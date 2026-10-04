from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.phone import phone_digits
from app.models.customer import Customer
from app.models.order import Order, OrderStatus


class CustomerRepository:
    def __init__(self, db: Session, tenant_id: UUID):
        self.db = db
        self.tenant_id = tenant_id

    def create(self, customer: Customer) -> Customer:
        customer.tenant_id = self.tenant_id
        customer.phone_digits = phone_digits(customer.phone)
        self.db.add(customer)
        self.db.flush()
        self.db.refresh(customer)
        return customer

    def get_by_id(self, customer_id: UUID) -> Customer | None:
        return self.db.scalar(select(Customer).where(
            Customer.tenant_id == self.tenant_id,
            Customer.id == customer_id,
            Customer.active.is_(True),
        ))

    def get_by_id_any_status(self, customer_id: UUID) -> Customer | None:
        return self.db.scalar(select(Customer).where(
            Customer.tenant_id == self.tenant_id,
            Customer.id == customer_id,
        ))

    def get_by_phone(self, phone: str, include_inactive: bool = False) -> Customer | None:
        digits = phone_digits(phone)
        if digits is None:
            return None
        statement = select(Customer).where(Customer.tenant_id == self.tenant_id, Customer.phone_digits == digits)
        if not include_inactive:
            statement = statement.where(Customer.active.is_(True))
        return self.db.scalar(statement)

    def get_or_create_by_phone(self, name: str, phone: str) -> Customer:
        """Finds the customer of this phone number or creates one; safe against two simultaneous orders."""
        customer = self.get_by_phone(phone, include_inactive=True)
        if customer is None:
            try:
                with self.db.begin_nested():
                    customer = self.create(Customer(name=name, phone=phone))
            except Exception:
                customer = self.get_by_phone(phone, include_inactive=True)
                if customer is None:
                    raise
        if not customer.active:
            customer.active = True
        if customer.name != name:
            customer.name = name
        return customer

    def search(
        self, q: str | None, active: bool | None, page: int, page_size: int, sort: str = "name"
    ) -> tuple[list[tuple[Customer, int, object, object]], int]:
        """Customers with their order stats, filtered and paginated."""
        stats = (
            select(
                Order.customer_id.label("customer_id"),
                func.count(Order.id).label("orders_count"),
                func.coalesce(func.sum(Order.total), 0).label("total_spent"),
                func.max(Order.created_at).label("last_order_at"),
            )
            .where(Order.tenant_id == self.tenant_id, Order.status != OrderStatus.CANCELLED)
            .group_by(Order.customer_id)
            .subquery()
        )
        conditions = [Customer.tenant_id == self.tenant_id]
        if active is not None:
            conditions.append(Customer.active.is_(active))
        if q:
            term = q.strip()
            digits = phone_digits(term)
            matches = [Customer.name.ilike(f"%{term}%")]
            if digits:
                matches.append(Customer.phone_digits.like(f"%{digits}%"))
            conditions.append(or_(*matches))

        total = int(self.db.scalar(select(func.count(Customer.id)).where(*conditions)) or 0)
        order_by = {
            "recent": stats.c.last_order_at.desc().nulls_last(),
            "spent": stats.c.total_spent.desc().nulls_last(),
        }.get(sort, Customer.name)
        rows = self.db.execute(
            select(
                Customer,
                func.coalesce(stats.c.orders_count, 0),
                func.coalesce(stats.c.total_spent, 0),
                stats.c.last_order_at,
            )
            .outerjoin(stats, stats.c.customer_id == Customer.id)
            .where(*conditions)
            .order_by(order_by, Customer.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
        return [tuple(row) for row in rows], total

    def update(self, customer: Customer) -> Customer:
        customer.phone_digits = phone_digits(customer.phone)
        self.db.flush()
        self.db.refresh(customer)
        return customer

    def delete(self, customer: Customer) -> Customer:
        customer.active = False
        return self.update(customer)
