from datetime import datetime
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.phone import phone_digits
from app.models.customer import Customer
from app.models.order import Order, OrderStatus, PaymentStatus, ServiceType

_ORDER_LOAD_OPTIONS = (
    selectinload(Order.items),
    selectinload(Order.status_history),
    selectinload(Order.customer),
)

ACTIVE_STATUSES = (OrderStatus.RECEIVED, OrderStatus.PREPARING, OrderStatus.READY)


class OrderRepository:
    def __init__(self, db: Session, tenant_id: UUID):
        self.db = db
        self.tenant_id = tenant_id

    def create(self, order: Order) -> Order:
        order.tenant_id = self.tenant_id
        self.db.add(order)
        self.db.flush()
        self.db.refresh(order)
        return order

    def get_by_id(self, order_id: UUID) -> Order | None:
        statement = select(Order).options(*_ORDER_LOAD_OPTIONS).where(
            Order.tenant_id == self.tenant_id,
            Order.id == order_id,
        )
        return self.db.scalar(statement)

    def get_by_public_token(self, public_token: UUID) -> Order | None:
        return self.db.scalar(
            select(Order).options(selectinload(Order.items)).where(
                Order.tenant_id == self.tenant_id,
                Order.public_token == public_token,
            )
        )

    def get_board(self, day_start: datetime, limit: int = 400) -> list[Order]:
        """Orders still in progress plus whatever was finished or cancelled since the day began."""
        statement = (
            select(Order)
            .options(*_ORDER_LOAD_OPTIONS)
            .where(
                Order.tenant_id == self.tenant_id,
                or_(Order.status.in_(ACTIVE_STATUSES), Order.updated_at >= day_start),
            )
            .order_by(Order.created_at.desc())
            .limit(limit)
        )
        return list(self.db.scalars(statement).all())

    def _filters(
        self,
        status: list[OrderStatus] | None,
        payment_status: PaymentStatus | None,
        service_type: ServiceType | None,
        date_from: datetime | None,
        date_to: datetime | None,
        q: str | None,
    ):
        conditions = [Order.tenant_id == self.tenant_id]
        if status:
            conditions.append(Order.status.in_(status))
        if payment_status:
            conditions.append(Order.payment_status == payment_status)
        if service_type:
            conditions.append(Order.service_type == service_type)
        if date_from:
            conditions.append(Order.created_at >= date_from)
        if date_to:
            conditions.append(Order.created_at < date_to)
        if q:
            term = q.strip().lstrip("#")
            matches = [Customer.name.ilike(f"%{term}%"), Order.table_label.ilike(f"%{term}%")]
            if term.isdigit():
                matches.append(Order.order_number == int(term))
            digits = phone_digits(term)
            if digits and len(digits) >= 4:
                matches.append(Customer.phone_digits.like(f"%{digits}%"))
            conditions.append(or_(*matches))
        return conditions

    def search(
        self,
        *,
        status: list[OrderStatus] | None = None,
        payment_status: PaymentStatus | None = None,
        service_type: ServiceType | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        q: str | None = None,
        page: int = 1,
        page_size: int = 25,
    ) -> tuple[list[Order], int]:
        conditions = self._filters(status, payment_status, service_type, date_from, date_to, q)
        base = select(Order).join(Customer, Customer.id == Order.customer_id).where(*conditions)
        total = int(self.db.scalar(
            select(func.count()).select_from(Order).join(Customer, Customer.id == Order.customer_id).where(*conditions)
        ) or 0)
        rows = self.db.scalars(
            base.options(*_ORDER_LOAD_OPTIONS)
            .order_by(Order.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
        return list(rows), total

    def export(self, limit: int = 5000, **filters) -> list[Order]:
        conditions = self._filters(
            filters.get("status"), filters.get("payment_status"), filters.get("service_type"),
            filters.get("date_from"), filters.get("date_to"), filters.get("q"),
        )
        statement = (
            select(Order)
            .join(Customer, Customer.id == Order.customer_id)
            .options(*_ORDER_LOAD_OPTIONS)
            .where(*conditions)
            .order_by(Order.created_at.desc())
            .limit(limit)
        )
        return list(self.db.scalars(statement).all())

    def get_recent_by_customer(self, customer_id: UUID, limit: int) -> list[Order]:
        statement = (
            select(Order)
            .options(selectinload(Order.items))
            .where(
                Order.tenant_id == self.tenant_id,
                Order.customer_id == customer_id,
                Order.status != OrderStatus.CANCELLED,
            )
            .order_by(Order.created_at.desc())
            .limit(limit)
        )
        return list(self.db.scalars(statement).all())

    def update(self, order: Order) -> Order:
        self.db.flush()
        self.db.refresh(order)
        return order
