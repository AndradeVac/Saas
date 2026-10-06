from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import BusinessRuleError, NotFoundError
from app.core.plans import can_take_orders, ensure_can_take_order
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
from app.services.audit import record_audit
from app.services.coupon import CouponService
from app.services.tab import TabService

_CENTS = Decimal("0.01")


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
        if data.payment_method is PaymentMethod.TAB and not on_tab:
            raise BusinessRuleError("Escolha a forma de pagamento.")

        if public:
            if not tenant.is_open:
                raise BusinessRuleError("O estabelecimento não está aceitando pedidos no momento.")
            if data.service_type.value not in tenant.enabled_services:
                raise BusinessRuleError("Este tipo de atendimento não está disponível.")
            if not on_tab and data.payment_method.value not in tenant.accepted_payments:
                raise BusinessRuleError("Esta forma de pagamento não está disponível.")
        if data.service_type is ServiceType.DELIVERY and not data.delivery_address:
            raise BusinessRuleError("Informe o endereço de entrega.")

        order = Order(
            customer_id=customer.id,
            payment_method=PaymentMethod.TAB if on_tab else data.payment_method,
            service_type=data.service_type,
            table_label=data.table_label if data.service_type is ServiceType.DINE_IN else None,
            delivery_address=data.delivery_address if data.service_type is ServiceType.DELIVERY else None,
            notes=data.notes,
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
        if data.service_type is ServiceType.DINE_IN and tenant.service_fee_percent > 0:
            service_fee = (taxable * tenant.service_fee_percent / 100).quantize(_CENTS, rounding=ROUND_HALF_UP)
        delivery_fee = tenant.delivery_fee if data.service_type is ServiceType.DELIVERY else Decimal("0.00")

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

        order.status = data.status
        order.status_history.append(
            OrderStatusHistory(status=data.status, reason=data.reason, changed_by_user_id=actor.id if actor else None)
        )
        if data.status is OrderStatus.CANCELLED:
            # A cancelled order gives its coupon use back.
            self.coupons.release(order.coupon_code)
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

        if data.payment_method is not None:
            order.payment_method = data.payment_method
        order.payment_status = data.payment_status
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
