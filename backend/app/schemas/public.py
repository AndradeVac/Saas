"""Payloads of the public (customer-facing) endpoints."""
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.core.phone import normalize_phone
from app.models.order import PaymentMethod, ServiceType
from app.schemas.order import SelectedOption
from app.schemas.product import OptionGroup
from app.schemas.tenant import PublicTenant


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
    available: bool
    options: list[OptionGroup]


class PublicMenu(BaseModel):
    tenant: PublicTenant
    categories: list[PublicCategory]
    products: list[PublicProduct]


class PublicOrderItem(BaseModel):
    product_id: UUID
    quantity: int = Field(gt=0, le=20)
    notes: str | None = Field(default=None, max_length=300)
    options: list[SelectedOption] = Field(default_factory=list, max_length=40)


class PublicOrderCreate(BaseModel):
    customer_name: str = Field(min_length=2, max_length=120)
    customer_phone: str = Field(min_length=10, max_length=20)
    service_type: ServiceType = ServiceType.DINE_IN
    table_label: str | None = Field(default=None, max_length=30)
    delivery_address: str | None = Field(default=None, max_length=300)
    payment_method: PaymentMethod = PaymentMethod.CASH
    notes: str | None = Field(default=None, max_length=500)
    coupon_code: str | None = Field(default=None, max_length=40)
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

    @field_validator("table_label", "delivery_address", "coupon_code")
    @classmethod
    def _strip_optional(cls, value: str | None) -> str | None:
        value = " ".join((value or "").split())
        return value or None


class PublicOrderResponse(BaseModel):
    order_number: int
    status: str
    total: str
    public_token: UUID
    payment_status: str
    # Set when the order joined the table's open bill (comanda); every phone at the table follows it.
    tab_token: UUID | None = None


class PublicHistoryItem(BaseModel):
    product_id: UUID
    product_name: str
    quantity: int
    options: list[dict] = []
    notes: str | None


class PublicOrderTracking(BaseModel):
    order_number: int
    status: str
    total: str
    subtotal: str
    discount: str
    service_fee: str
    delivery_fee: str
    created_at: datetime
    payment_status: str
    payment_method: str
    service_type: str
    table_label: str | None
    delivery_address: str | None
    items: list[PublicHistoryItem]


class PublicHistoryOrder(BaseModel):
    order_number: int
    public_token: UUID
    status: str
    total: str
    created_at: datetime
    items: list[PublicHistoryItem]


class CouponCheckRequest(BaseModel):
    code: str = Field(min_length=1, max_length=40)
    subtotal: Decimal = Field(ge=0, max_digits=12, decimal_places=2)


class CouponCheckResponse(BaseModel):
    code: str
    discount: Decimal
