from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.models.customer import Customer
from app.repositories.customer import CustomerRepository
from app.schemas.customer import CustomerCreate, CustomerUpdate


class CustomerService:
    def __init__(self, db: Session, tenant_id: UUID):
        self.repository = CustomerRepository(db, tenant_id)
        self.db = db

    def create(self, data: CustomerCreate) -> Customer:
        customer = Customer(name=data.name, phone=data.phone)
        self.repository.create(customer)
        self.db.commit()
        return customer

    def get_by_id(self, customer_id: UUID) -> Customer:
        customer = self.repository.get_by_id(customer_id)
        if customer is None:
            raise NotFoundError("Cliente não encontrado.")
        return customer

    def get_all(self) -> list[Customer]:
        return self.repository.get_all()

    def update(self, customer_id: UUID, data: CustomerUpdate) -> Customer:
        customer = self.repository.get_by_id_any_status(customer_id)
        if customer is None:
            raise NotFoundError("Cliente não encontrado.")

        if data.name is not None:
            customer.name = data.name
        if "phone" in data.model_fields_set:
            customer.phone = data.phone
        if data.active is not None:
            customer.active = data.active

        self.repository.update(customer)
        self.db.commit()
        return customer

    def delete(self, customer_id: UUID) -> Customer:
        customer = self.get_by_id(customer_id)
        self.repository.delete(customer)
        self.db.commit()
        return customer
