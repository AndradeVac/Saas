"""Payloads of the public (customer-facing) endpoints."""
import re
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.models.order import PaymentMethod, ServiceType
from app.schemas.tenant import PublicTenant


def normalize_phone(value: str) -> str:
    """Keep digits only, so "(11) 99999-9999" and "11999999999" are the same customer."""
    digits = re.sub(r"\D", "", value)
    if digits.startswith("55") and len(digits) in (12, 13):
        digits = digits[2:]
    if len(digits) not in (10, 11):
        raise ValueError("Informe um telefone válido com DDD.")
    return digits


class PublicCategory(BaseModel):
    id: UUID
    name: str
    image_url: str | None = None


class PublicProduct(BaseModel):
    id: UUID
    category_id: UUID
    name: str
    description: str | None
    image_url: str | None = None
    price: Decimal
    featured: bool


class PublicMenu(BaseModel):
    tenant: PublicTenant
    categories: list[PublicCategory]
    products: list[PublicProduct]


class PublicOrderItem(BaseModel):
    product_id: UUID
    quantity: int = Field(gt=0, le=20)
    notes: str | None = Field(default=None, max_length=300)


class PublicOrderCreate(BaseModel):
    customer_name: str = Field(min_length=2, max_length=120)
    customer_phone: str = Field(min_length=10, max_length=20)
    service_type: ServiceType = ServiceType.DINE_IN
    table_label: str | None = Field(default=None, max_length=30)
    payment_method: PaymentMethod = PaymentMethod.CASH
    notes: str | None = Field(default=None, max_length=500)
    items: list[PublicOrderItem] = Field(min_length=1, max_length=30)

    @field_validator("customer_name")
    @classmethod
    def _strip_name(cls, value: str) -> str:
        value = " ".join(value.split())
        if len(value) < 2:
            raise ValueError("Informe seu nome.")
        return value

    @field_validator("customer_phone")
    @classmethod
    def _normalize_phone(cls, value: str) -> str:
        return normalize_phone(value)

    @field_validator("table_label")
    @classmethod
    def _strip_table(cls, value: str | None) -> str | None:
        value = " ".join((value or "").split())
        return value or None


class PublicOrderResponse(BaseModel):
    order_number: int
    status: str
    total: str
    public_token: UUID
    payment_status: str


class PublicOrderTracking(BaseModel):
    order_number: int
    status: str
    total: str
    created_at: datetime
    payment_status: str
    service_type: str
    table_label: str | None
    items: list["PublicHistoryItem"]


class PublicHistoryItem(BaseModel):
    product_id: UUID
    product_name: str
    quantity: int
    notes: str | None


class PublicHistoryOrder(BaseModel):
    order_number: int
    public_token: UUID
    status: str
    total: str
    created_at: datetime
    items: list[PublicHistoryItem]


PublicOrderTracking.model_rebuild()
