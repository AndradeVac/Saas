from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.models.order import PaymentMethod
from app.models.tab import TabStatus


def _real_payment(value: PaymentMethod | None) -> PaymentMethod | None:
    if value is PaymentMethod.TAB:
        raise ValueError("Escolha como a conta será paga.")
    return value


class TabOrderItem(BaseModel):
    product_id: UUID
    product_name: str
    quantity: int
    options: list[dict] = []
    notes: str | None = None


class TabOrder(BaseModel):
    id: UUID
    order_number: int
    status: str
    customer_name: str | None
    total: Decimal
    created_at: datetime
    items: list[TabOrderItem]


class TabTotals(BaseModel):
    subtotal: Decimal
    discount: Decimal
    service_fee: Decimal
    total: Decimal
    # total / split_count, when the customer chose to split the bill.
    per_person: Decimal | None


class TabAlerts(BaseModel):
    """Automations: what the floor staff should act on now."""

    needs_approval: bool
    wants_to_close: bool
    # Nothing new for `tab_idle_minutes` and nothing cooking: time to offer another round.
    idle: bool
    # Orders waiting in the kitchen for more than LATE_ORDER_MINUTES.
    late_orders: int
    minutes_open: int
    minutes_since_last_order: int | None


class TabResponse(BaseModel):
    id: UUID
    number: int
    public_token: UUID
    table_label: str
    status: TabStatus
    opened_by: str | None
    requested_payment_method: PaymentMethod | None
    split_count: int | None
    payment_method: PaymentMethod | None
    created_at: datetime
    last_order_at: datetime | None
    close_requested_at: datetime | None
    closed_at: datetime | None
    totals: TabTotals
    orders: list[TabOrder]
    alerts: TabAlerts


class PublicTab(BaseModel):
    number: int
    public_token: UUID
    table_label: str
    status: TabStatus
    requested_payment_method: PaymentMethod | None
    split_count: int | None
    last_order_at: datetime | None
    totals: TabTotals
    orders: list[TabOrder]


class TabCloseRequest(BaseModel):
    """Customer asks for the bill."""

    payment_method: PaymentMethod
    split_count: int | None = Field(default=None, ge=1, le=30)

    _validate_payment = field_validator("payment_method")(_real_payment)


class TabClose(BaseModel):
    """Staff received the payment."""

    payment_method: PaymentMethod

    _validate_payment = field_validator("payment_method")(_real_payment)


class TabReason(BaseModel):
    reason: str = Field(min_length=2, max_length=200)
