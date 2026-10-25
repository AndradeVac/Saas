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
    total_price: Decimal = Decimal("0")  # lets each person pay only what they ate


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
    paid: Decimal = Decimal("0.00")  # confirmed payments
    reported: Decimal = Decimal("0.00")  # PIX the customers say they sent, waiting for staff to confirm
    remaining: Decimal = Decimal("0.00")


class TabPaymentOut(BaseModel):
    id: UUID
    amount: Decimal
    method: PaymentMethod
    status: str
    payer_name: str | None
    created_at: datetime


class TabAlerts(BaseModel):
    """Automations: what the floor staff should act on now."""

    needs_approval: bool
    wants_to_close: bool
    # Nothing new for `tab_idle_minutes` and nothing cooking: time to offer another round.
    idle: bool
    # Orders waiting in the kitchen for more than LATE_ORDER_MINUTES.
    late_orders: int
    # PIX payments reported by customers that staff still has to check.
    payments_to_confirm: int = 0
    # The table called the waiter: reason (GARCOM, CONTA, GUARDANAPO, TALHERES, OUTRO) until someone answers.
    waiter_call: str | None = None
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
    service_fee_waived: bool = False
    payment_method: PaymentMethod | None
    created_at: datetime
    last_order_at: datetime | None
    close_requested_at: datetime | None
    closed_at: datetime | None
    totals: TabTotals
    orders: list[TabOrder]
    payments: list[TabPaymentOut] = []
    alerts: TabAlerts


class PublicTab(BaseModel):
    number: int
    public_token: UUID
    table_label: str
    status: TabStatus
    requested_payment_method: PaymentMethod | None
    split_count: int | None
    service_fee_waived: bool = False
    waiter_call: str | None = None
    last_order_at: datetime | None
    totals: TabTotals
    orders: list[TabOrder]
    payments: list[TabPaymentOut] = []


class WaiterCall(BaseModel):
    reason: str = Field(pattern="^(GARCOM|CONTA|GUARDANAPO|TALHERES|OUTRO)$")


class ServiceFeeChoice(BaseModel):
    waived: bool


class TabCloseRequest(BaseModel):
    """Customer asks for the bill."""

    payment_method: PaymentMethod
    split_count: int | None = Field(default=None, ge=1, le=30)

    _validate_payment = field_validator("payment_method")(_real_payment)


class TabClose(BaseModel):
    """Staff received the payment."""

    payment_method: PaymentMethod

    _validate_payment = field_validator("payment_method")(_real_payment)


class PixCode(BaseModel):
    code: str  # PIX copia e cola (also rendered as a QR Code)
    amount: Decimal


class PixReport(BaseModel):
    amount: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    payer_name: str | None = Field(default=None, max_length=120)


class TabPaymentCreate(BaseModel):
    """Staff records a share paid in cash/card (or PIX checked in the bank)."""

    amount: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    payment_method: PaymentMethod

    _validate_payment = field_validator("payment_method")(_real_payment)


class TableQr(BaseModel):
    label: str
    code: str
    url: str


class TabReason(BaseModel):
    reason: str = Field(min_length=2, max_length=200)
