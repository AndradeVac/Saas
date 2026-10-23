from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.tables import normalize_table_label

from app.models.order import OrderStatus, PaymentMethod, PaymentStatus, ServiceType


class SelectedOption(BaseModel):
    group_id: str = Field(max_length=40)
    option_id: str = Field(max_length=40)


class OrderItemCreate(BaseModel):
    product_id: UUID
    quantity: int = Field(gt=0, le=50)
    notes: str | None = Field(default=None, max_length=300)
    options: list[SelectedOption] = Field(default_factory=list, max_length=40)


class OrderCreate(BaseModel):
    customer_id: UUID
    payment_method: PaymentMethod
    service_type: ServiceType = ServiceType.DINE_IN
    table_label: str | None = Field(default=None, max_length=30)
    # Code from the table's QR Code; required for customers ordering on a table's bill (comanda).
    table_code: str | None = Field(default=None, max_length=20)
    delivery_address: str | None = Field(default=None, max_length=300)
    notes: str | None = Field(default=None, max_length=500)
    coupon_code: str | None = Field(default=None, max_length=40)
    # The service fee (tip) is optional: the customer can take it out.
    waive_service_fee: bool = False
    delivery_zone: str | None = Field(default=None, max_length=60)  # neighbourhood, when the store set delivery zones
    scheduled_for: datetime | None = None  # encomenda
    notify_whatsapp: bool = False
    items: list[OrderItemCreate] = Field(min_length=1, max_length=60)

    @field_validator("table_label")
    @classmethod
    def _normalize_table(cls, value: str | None) -> str | None:
        return normalize_table_label(value)


class OrderItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    product_id: UUID
    product_name: str
    quantity: int
    unit_price: Decimal
    total_price: Decimal
    options: list[dict]
    notes: str | None
    created_at: datetime


class OrderStatusHistoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    status: OrderStatus
    changed_by_user_id: UUID | None
    created_at: datetime
    reason: str | None


class OrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    order_number: int
    customer_id: UUID
    customer_name: str | None = None
    customer_phone: str | None = None
    status: OrderStatus
    service_type: ServiceType
    table_label: str | None
    tab_id: UUID | None = None
    delivery_address: str | None
    payment_method: PaymentMethod
    payment_status: PaymentStatus
    paid_at: datetime | None
    scheduled_for: datetime | None = None
    notes: str | None
    coupon_code: str | None
    subtotal: Decimal
    discount: Decimal
    service_fee: Decimal
    delivery_fee: Decimal
    total: Decimal
    created_at: datetime
    updated_at: datetime
    items: list[OrderItemResponse]
    status_history: list[OrderStatusHistoryResponse]


class OrderStatusUpdate(BaseModel):
    status: OrderStatus
    reason: str | None = Field(default=None, max_length=500)


class OrderPaymentUpdate(BaseModel):
    payment_status: PaymentStatus
    payment_method: PaymentMethod | None = None


class OrderEdit(BaseModel):
    table_label: str | None = Field(default=None, max_length=30)
    notes: str | None = Field(default=None, max_length=500)
    delivery_address: str | None = Field(default=None, max_length=300)
