from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import BusinessRuleError, NotFoundError
from app.models.order import Order, OrderStatus, PaymentStatus
from app.models.order_item import OrderItem
from app.models.order_status_history import OrderStatusHistory
from app.models.user import User
from app.repositories.customer import CustomerRepository
from app.repositories.order import OrderRepository
from app.repositories.product import ProductRepository
from app.repositories.tenant import TenantRepository
from app.schemas.order import OrderCreate, OrderPaymentUpdate, OrderStatusUpdate
from app.services.audit import record_audit


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
        self.tenant_id = tenant_id
        self.db = db

    def create(self, data: OrderCreate, actor: User | None = None) -> Order:
        customer = self.customer_repository.get_by_id(data.customer_id)
        if customer is None:
            raise NotFoundError("Cliente não encontrado.")

        order = Order(
            customer_id=customer.id,
            payment_method=data.payment_method,
            service_type=data.service_type,
            table_label=data.table_label,
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

            total_price = (product.price * item_data.quantity).quantize(Decimal("0.01"))
            subtotal += total_price
            order.items.append(
                OrderItem(
                    product_id=product.id,
                    product_name=product.name,
                    quantity=item_data.quantity,
                    unit_price=product.price,
                    total_price=total_price,
                    notes=item_data.notes,
                )
            )

        order.subtotal = subtotal
        order.total = subtotal
        order.status_history.append(OrderStatusHistory(status=OrderStatus.RECEIVED, changed_by_user_id=actor.id if actor else None))

        try:
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

    def get_all(self, limit: int | None = None) -> list[Order]:
        return self.repository.get_all(limit=limit)

    def update_status(self, order_id: UUID, data: OrderStatusUpdate, actor: User | None = None) -> Order:
        order = self.get_by_id(order_id)

        if data.status not in self.allowed_transitions[order.status]:
            raise BusinessRuleError(f"Não é possível alterar {order.status.value} para {data.status.value}.")
        if data.status is OrderStatus.CANCELLED and not data.reason:
            raise BusinessRuleError("Informe o motivo do cancelamento.")

        order.status = data.status
        order.status_history.append(
            OrderStatusHistory(
                status=data.status,
                reason=data.reason,
                changed_by_user_id=actor.id if actor else None,
            )
        )
        record_audit(self.db, self.tenant_id, actor, "ORDER_STATUS_CHANGED", "ORDER", order.id, f"status={data.status.value}")
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

        if data.payment_method is not None:
            order.payment_method = data.payment_method
        order.payment_status = data.payment_status
        order.paid_at = datetime.now(timezone.utc) if data.payment_status is PaymentStatus.PAID else None
        record_audit(
            self.db, self.tenant_id, actor, "ORDER_PAYMENT_CHANGED", "ORDER", order.id,
            f"payment={data.payment_status.value} method={order.payment_method.value}",
        )
        self.repository.update(order)
        self.db.commit()
        return order
