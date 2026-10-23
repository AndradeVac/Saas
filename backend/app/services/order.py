from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import BusinessRuleError, NotFoundError
from app.core.pix import brcode, normalize_pix_key
from app.core.plans import can_take_orders, ensure_can_take_order
from app.core.tables import valid_table_code
from app.models.order import Order, OrderStatus, PaymentMethod, PaymentStatus, ServiceType
from app.models.order_item import OrderItem
from app.models.order_status_history import OrderStatusHistory
from app.models.product import Product
from app.models.tenant import Tenant
from app.models.user import User
from app.repositories.customer import CustomerRepository
from app.repositories.order import OrderRepository
from app.repositories.product import ProductRepository
from app.repositories.tenant import TenantRepository
from app.schemas.order import OrderCreate, OrderEdit, OrderItemCreate, OrderPaymentUpdate, OrderStatusUpdate
from app.schemas.tab import PixCode
from app.services.audit import record_audit
from app.services.coupon import CouponService
from app.services.tab import TabService

_CENTS = Decimal("0.01")


def _category_open(category, tenant: Tenant, at: datetime | None = None) -> bool:
    """Menu by time of day: a category with a window is only sold inside it (window may cross midnight)."""
    if category is None or not (category.available_from and category.available_until):
        return True
    moment = (at or datetime.now(timezone.utc)).astimezone(ZoneInfo(tenant.timezone)).time()
    start, end = category.available_from, category.available_until
    return start <= moment < end if start < end else moment >= start or moment < end


def awaiting_pix(order: Order, tenant: Tenant) -> bool:
    """Takeaway paid by PIX (and deliveries, when the store requires PIX up front): the kitchen only starts once
    the PIX is in."""
    prepaid = order.service_type is ServiceType.TAKEAWAY or (order.service_type is ServiceType.DELIVERY and tenant.require_pix_delivery)
    return (
        prepaid and order.payment_method is PaymentMethod.PIX
        and order.payment_status is not PaymentStatus.PAID and order.status is OrderStatus.RECEIVED
        and order.tab_id is None and bool(normalize_pix_key(tenant.pix_key or ""))
    )


def resolve_options(product: Product, item: OrderItemCreate) -> tuple[list[dict], Decimal]:
    """Validates the customer's choices against the product's option groups.
    Returns the snapshot stored on the order item and the extra price per unit."""
    groups = {group["id"]: group for group in (product.options or [])}
    chosen: dict[str, list[dict]] = {group_id: [] for group_id in groups}

    for selected in item.options:
        group = groups.get(selected.group_id)
        option = next((o for o in group["options"] if o["id"] == selected.option_id and o.get("active", True)), None) if group else None
        if option is None:
            raise BusinessRuleError(f"Uma das opções escolhidas para “{product.name}” não está mais disponível.")
        if any(o["id"] == option["id"] for o in chosen[group["id"]]):
            raise BusinessRuleError(f"Opção repetida em “{group['name']}”.")
        chosen[group["id"]].append(option)

    snapshot: list[dict] = []
    extra = Decimal("0")
    for group_id, group in groups.items():
        picks = chosen[group_id]
        minimum = max(int(group.get("min", 0)), 1 if group.get("required") else 0)
        if len(picks) < minimum:
            raise BusinessRuleError(f"Escolha {'uma opção' if minimum == 1 else f'pelo menos {minimum} opções'} em “{group['name']}” ({product.name}).")
        if len(picks) > int(group.get("max", 1)):
            raise BusinessRuleError(f"Você escolheu opções demais em “{group['name']}” ({product.name}).")
        for option in picks:
            price = Decimal(str(option.get("price", "0")))
            extra += price
            snapshot.append({"group": group["name"], "name": option["name"], "price": str(price)})
    return snapshot, extra


class OrderService:
    allowed_transitions = {
        OrderStatus.RECEIVED: {OrderStatus.PREPARING, OrderStatus.CANCELLED},
        OrderStatus.PREPARING: {OrderStatus.READY, OrderStatus.CANCELLED},
        OrderStatus.READY: {OrderStatus.FINISHED, OrderStatus.CANCELLED},
        OrderStatus.FINISHED: set(),
        OrderStatus.CANCELLED: set(),
    }

    def __init__(self, db: Session, tenant_id: UUID):
        self.repository = OrderRepository(db, tenant_id)
        self.customer_repository = CustomerRepository(db, tenant_id)
        self.product_repository = ProductRepository(db, tenant_id)
        self.tenant_repository = TenantRepository(db)
        self.coupons = CouponService(db, tenant_id)
        self.tenant_id = tenant_id
        self.db = db

    def _tenant(self) -> Tenant:
        tenant = self.tenant_repository.get_by_id(self.tenant_id)
        if tenant is None:
            raise NotFoundError("Estabelecimento não encontrado.")
        return tenant

    def create(self, data: OrderCreate, actor: User | None = None, public: bool = False) -> Order:
        """Prices and stores an order. `public=True` (customer menu) also enforces the business rules the
        owner configured: open hours, enabled services and payment methods, minimum order."""
        tenant = self._tenant()
        if public and not can_take_orders(self.db, tenant):
            # The customer only needs to know ordering is off; the owner sees the reason in the panel.
            raise BusinessRuleError("O estabelecimento não está aceitando pedidos no momento.")
        ensure_can_take_order(self.db, tenant)
        customer = self.customer_repository.get_by_id(data.customer_id)
        if customer is None:
            raise NotFoundError("Cliente não encontrado.")

        # Comanda: with tabs on, a dine-in order joins its table's open bill and is paid when the bill closes.
        on_tab = tenant.tabs_enabled and data.service_type is ServiceType.DINE_IN
        if on_tab and not data.table_label:
            raise BusinessRuleError("Informe o número da mesa.")
        if on_tab and public and not valid_table_code(tenant.table_secret, data.table_label, data.table_code):
            # Only someone looking at the QR Code on that table can order on its bill.
            raise BusinessRuleError("Para pedir na mesa, leia o QR Code que está nela.")
        if data.payment_method is PaymentMethod.TAB and not on_tab:
            raise BusinessRuleError("Escolha a forma de pagamento.")

        scheduled_for = None
        if data.scheduled_for is not None:
            # Encomenda: at least 30 minutes ahead, at most 30 days; may be placed while the store is closed.
            if not tenant.scheduling_enabled:
                raise BusinessRuleError("Este estabelecimento não aceita pedidos agendados.")
            when = data.scheduled_for if data.scheduled_for.tzinfo else data.scheduled_for.replace(tzinfo=ZoneInfo(tenant.timezone))
            now = datetime.now(timezone.utc)
            if when < now + timedelta(minutes=30) or when > now + timedelta(days=30):
                raise BusinessRuleError("Agende para pelo menos 30 minutos a partir de agora (até 30 dias).")
            scheduled_for = when
        if public:
            if not tenant.is_open and scheduled_for is None:
                raise BusinessRuleError("O estabelecimento não está aceitando pedidos no momento.")
            if data.service_type.value not in tenant.enabled_services:
                raise BusinessRuleError("Este tipo de atendimento não está disponível.")
            if not on_tab and data.payment_method.value not in tenant.accepted_payments:
                raise BusinessRuleError("Esta forma de pagamento não está disponível.")
        if data.service_type is ServiceType.DELIVERY and not data.delivery_address:
            raise BusinessRuleError("Informe o endereço de entrega.")
        zone = None
        if data.service_type is ServiceType.DELIVERY and tenant.delivery_zones:
            zone = next((z for z in tenant.delivery_zones if z["name"].lower() == (data.delivery_zone or "").strip().lower()), None)
            if zone is None:
                raise BusinessRuleError("Escolha o seu bairro. Só entregamos nos bairros da lista.")
        if public and data.service_type is ServiceType.DELIVERY and tenant.require_pix_delivery and data.payment_method is not PaymentMethod.PIX:
            raise BusinessRuleError("Para entrega, o pagamento é pelo PIX, antes do preparo.")

        order = Order(
            customer_id=customer.id,
            payment_method=PaymentMethod.TAB if on_tab else data.payment_method,
            service_type=data.service_type,
            table_label=data.table_label if data.service_type is ServiceType.DINE_IN else None,
            delivery_address=(f"{data.delivery_address.strip()} · {zone['name']}" if zone else data.delivery_address)
            if data.service_type is ServiceType.DELIVERY else None,
            notes=data.notes,
            scheduled_for=scheduled_for,
            status=OrderStatus.RECEIVED,
            subtotal=Decimal("0.00"),
            total=Decimal("0.00"),
        )

        subtotal = Decimal("0.00")
        for item_data in data.items:
            product = self.product_repository.get_by_id(item_data.product_id)
            if product is None:
                raise NotFoundError("Um dos produtos do pedido não está mais disponível.")
            if not product.available:
                raise BusinessRuleError(f"“{product.name}” está esgotado no momento.")
            if public and not _category_open(product.category, tenant, scheduled_for):
                raise BusinessRuleError(f"“{product.name}” só está disponível das {product.category.available_from:%H:%M} às {product.category.available_until:%H:%M}.")

            options, extra = resolve_options(product, item_data)
            unit_price = (product.price + extra).quantize(_CENTS)
            total_price = (unit_price * item_data.quantity).quantize(_CENTS)
            subtotal += total_price
            order.items.append(
                OrderItem(
                    product_id=product.id,
                    product_name=product.name,
                    quantity=item_data.quantity,
                    unit_price=unit_price,
                    total_price=total_price,
                    options=options,
                    notes=item_data.notes,
                )
            )

        # The minimum order is about the visit, not each round of a table's bill.
        if public and not on_tab and subtotal < tenant.min_order_value:
            raise BusinessRuleError(f"O pedido mínimo é de R$ {tenant.min_order_value:.2f}.".replace(".", ",", 1))

        discount = Decimal("0.00")
        if data.coupon_code:
            coupon, discount = self.coupons.validate(data.coupon_code, subtotal)
            self.coupons.consume(coupon)
            order.coupon_code = coupon.code

        taxable = subtotal - discount
        service_fee = Decimal("0.00")
        if data.service_type is ServiceType.DINE_IN and tenant.service_fee_percent > 0 and not data.waive_service_fee:
            service_fee = (taxable * tenant.service_fee_percent / 100).quantize(_CENTS, rounding=ROUND_HALF_UP)
        delivery_fee = Decimal("0.00")
        if data.service_type is ServiceType.DELIVERY:
            delivery_fee = Decimal(zone["fee"]) if zone else tenant.delivery_fee

        order.subtotal = subtotal
        order.discount = discount
        order.service_fee = service_fee
        order.delivery_fee = delivery_fee
        order.total = taxable + service_fee + delivery_fee
        order.status_history.append(OrderStatusHistory(status=OrderStatus.RECEIVED, changed_by_user_id=actor.id if actor else None))

        try:
            if on_tab:
                tab = TabService(self.db, self.tenant_id).attach(tenant, data.table_label, customer.name, by_staff=not public)
                order.tab_id = tab.id
                if tab.service_fee_waived and order.service_fee:
                    order.total -= order.service_fee
                    order.service_fee = Decimal("0.00")
            order.order_number = self.tenant_repository.next_order_number(self.tenant_id)
            self.repository.create(order)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return order

    def get_by_id(self, order_id: UUID) -> Order:
        order = self.repository.get_by_id(order_id)
        if order is None:
            raise NotFoundError("Pedido não encontrado.")
        return order

    def update_status(self, order_id: UUID, data: OrderStatusUpdate, actor: User | None = None) -> Order:
        order = self.get_by_id(order_id)

        if data.status not in self.allowed_transitions[order.status]:
            raise BusinessRuleError(f"Não é possível alterar {order.status.value} para {data.status.value}.")
        if data.status is OrderStatus.CANCELLED and not data.reason:
            raise BusinessRuleError("Informe o motivo do cancelamento.")
        if data.status is not OrderStatus.CANCELLED and awaiting_pix(order, self.db.get(Tenant, self.tenant_id)):
            raise BusinessRuleError("Aguardando o PIX do cliente. Confirme o pagamento para iniciar o preparo.")

        order.status = data.status
        order.status_history.append(
            OrderStatusHistory(status=data.status, reason=data.reason, changed_by_user_id=actor.id if actor else None)
        )
        if data.status is OrderStatus.CANCELLED:
            # A cancelled order gives its coupon use back.
            self.coupons.release(order.coupon_code)
            if order.tab_id:
                TabService(self.db, self.tenant_id).cancel_if_empty(order.tab_id, actor)
        record_audit(self.db, self.tenant_id, actor, "ORDER_STATUS_CHANGED", "ORDER", order.id, f"#{order.order_number} status={data.status.value}")
        try:
            self.repository.update(order)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return order

    def update_payment(self, order_id: UUID, data: OrderPaymentUpdate, actor: User | None = None) -> Order:
        """Staff confirms (or reverts) the payment received at the counter."""
        order = self.get_by_id(order_id)
        if order.status is OrderStatus.CANCELLED:
            raise BusinessRuleError("Pedidos cancelados não podem receber pagamento.")
        if order.tab_id:
            raise BusinessRuleError("Este pedido é pago junto com a comanda da mesa. Feche a conta em Mesas.")

        was_waiting = awaiting_pix(order, self.db.get(Tenant, self.tenant_id))
        if data.payment_method is not None:
            order.payment_method = data.payment_method
        order.payment_status = data.payment_status
        if was_waiting and data.payment_status is PaymentStatus.PAID:
            # PIX confirmed: the order goes straight to the kitchen.
            order.status = OrderStatus.PREPARING
            order.status_history.append(OrderStatusHistory(status=OrderStatus.PREPARING, changed_by_user_id=actor.id if actor else None))
        order.paid_at = datetime.now(timezone.utc) if data.payment_status is PaymentStatus.PAID else None
        record_audit(
            self.db, self.tenant_id, actor, "ORDER_PAYMENT_CHANGED", "ORDER", order.id,
            f"#{order.order_number} payment={data.payment_status.value} method={order.payment_method.value}",
        )
        self.repository.update(order)
        self.db.commit()
        return order

    def edit(self, order_id: UUID, data: OrderEdit, actor: User | None = None) -> Order:
        order = self.get_by_id(order_id)
        if order.status in (OrderStatus.FINISHED, OrderStatus.CANCELLED):
            raise BusinessRuleError("Pedidos encerrados não podem ser editados.")
        if order.tab_id and "table_label" in data.model_fields_set and data.table_label != order.table_label:
            raise BusinessRuleError("Este pedido está na comanda da mesa; a mesa não pode ser trocada por aqui.")
        for field in data.model_fields_set:
            setattr(order, field, getattr(data, field) or None)
        record_audit(self.db, self.tenant_id, actor, "ORDER_EDITED", "ORDER", order.id, f"#{order.order_number}")
        self.repository.update(order)
        self.db.commit()
        return order

    def cancel_by_customer(self, public_token: UUID) -> Order:
        """The customer gives up before the kitchen starts (and before paying): no phone call needed."""
        order = self.repository.get_by_public_token(public_token)
        if order is None:
            raise NotFoundError("Pedido não encontrado.")
        if order.status is not OrderStatus.RECEIVED or order.payment_status is PaymentStatus.PAID or order.tab_id:
            raise BusinessRuleError("Este pedido já está em preparo. Fale com o estabelecimento.")
        order.status = OrderStatus.CANCELLED
        order.status_history.append(OrderStatusHistory(status=OrderStatus.CANCELLED, reason="Cancelado pelo cliente"))
        self.coupons.release(order.coupon_code)
        record_audit(self.db, self.tenant_id, None, "ORDER_STATUS_CHANGED", "ORDER", order.id, f"#{order.order_number} cancelado pelo cliente")
        self.db.commit()
        return order

    def pix_code(self, public_token: UUID, tenant: Tenant) -> PixCode:
        """PIX copia e cola with the order's exact total, paid straight to the restaurant's key."""
        order = self.repository.get_by_public_token(public_token)
        if order is None:
            raise NotFoundError("Pedido não encontrado.")
        if order.payment_method is not PaymentMethod.PIX or order.payment_status is PaymentStatus.PAID or order.status is OrderStatus.CANCELLED:
            raise BusinessRuleError("Este pedido não está aguardando pagamento por PIX.")
        key = normalize_pix_key(tenant.pix_key or "")
        if not key:
            raise BusinessRuleError("Este estabelecimento ainda não cadastrou a chave PIX. Pague no caixa.")
        return PixCode(code=brcode(key, order.total, tenant.name, tenant.city or "BRASIL", f"PED{order.order_number}"), amount=order.total)

