from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import BusinessRuleError, NotFoundError
from app.core.phone import normalize_phone
from app.models.customer import Customer
from app.repositories.customer import CustomerRepository
from app.schemas.customer import CustomerCreate, CustomerListItem, CustomerUpdate


def _clean_phone(phone: str | None) -> str | None:
    if not phone or not phone.strip():
        return None
    try:
        return normalize_phone(phone)
    except ValueError as error:
        raise BusinessRuleError(str(error)) from error


class CustomerService:
    def __init__(self, db: Session, tenant_id: UUID):
        self.repository = CustomerRepository(db, tenant_id)
        self.db = db

    def create(self, data: CustomerCreate) -> Customer:
        phone = _clean_phone(data.phone)
        if phone and self.repository.get_by_phone(phone, include_inactive=True) is not None:
            raise BusinessRuleError("Já existe um cliente com esse telefone.")
        customer = Customer(name=data.name.strip(), phone=phone, notes=data.notes)
        self.repository.create(customer)
        self.db.commit()
        return customer

    def get_by_id(self, customer_id: UUID) -> Customer:
        customer = self.repository.get_by_id_any_status(customer_id)
        if customer is None:
            raise NotFoundError("Cliente não encontrado.")
        return customer

    def search(self, q: str | None, active: bool | None, page: int, page_size: int, sort: str):
        rows, total = self.repository.search(q, active, page, page_size, sort)
        items = [
            CustomerListItem.model_validate(customer).model_copy(
                update={"orders_count": int(count), "total_spent": spent, "last_order_at": last}
            )
            for customer, count, spent, last in rows
        ]
        return items, total

    def update(self, customer_id: UUID, data: CustomerUpdate) -> Customer:
        customer = self.get_by_id(customer_id)

        if data.name is not None:
            customer.name = data.name.strip()
        if "phone" in data.model_fields_set:
            phone = _clean_phone(data.phone)
            other = self.repository.get_by_phone(phone, include_inactive=True) if phone else None
            if other is not None and other.id != customer.id:
                raise BusinessRuleError("Já existe um cliente com esse telefone.")
            customer.phone = phone
        if "notes" in data.model_fields_set:
            customer.notes = data.notes
        if data.active is not None:
            customer.active = data.active

        self.repository.update(customer)
        self.db.commit()
        return customer
