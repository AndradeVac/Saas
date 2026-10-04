import re
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.customer import Customer


class CustomerRepository:
    def __init__(self, db: Session, tenant_id: UUID):
        self.db = db
        self.tenant_id = tenant_id

    def create(self, customer: Customer) -> Customer:
        customer.tenant_id = self.tenant_id
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

    def get_by_phone(self, phone: str) -> Customer | None:
        """Match by digits only, ignoring how the stored phone was formatted."""
        digits = re.sub(r"\D", "", phone)
        if not digits:
            return None
        statement = (
            select(Customer)
            .where(
                Customer.tenant_id == self.tenant_id,
                func.regexp_replace(Customer.phone, r"\D", "", "g") == digits,
                Customer.active.is_(True),
            )
            .order_by(Customer.created_at)
            .limit(1)
        )
        return self.db.scalar(statement)

    def get_all(self) -> list[Customer]:
        statement = (
            select(Customer)
            .where(Customer.tenant_id == self.tenant_id)
            .order_by(Customer.active.desc(), Customer.name)
        )
        return list(self.db.scalars(statement).all())

    def update(self, customer: Customer) -> Customer:
        self.db.flush()
        self.db.refresh(customer)
        return customer

    def delete(self, customer: Customer) -> Customer:
        customer.active = False
        return self.update(customer)
