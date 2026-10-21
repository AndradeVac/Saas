import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, ForeignKeyConstraint, Index, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.order import PaymentMethod


class TabPaymentStatus(str, enum.Enum):
    REPORTED = "REPORTED"  # customer says they paid (PIX); staff must check the bank and confirm
    CONFIRMED = "CONFIRMED"  # money received
    REJECTED = "REJECTED"  # staff did not find the payment


class TabPayment(Base):
    """A payment towards a table's bill: the whole bill or one person's share."""

    __tablename__ = "tab_payments"
    __table_args__ = (
        CheckConstraint("amount > 0", name="chk_tab_payments_amount"),
        ForeignKeyConstraint(["tenant_id", "tab_id"], ["tabs.tenant_id", "tabs.id"], name="fk_tab_payments_tenant_tab", ondelete="CASCADE"),
        Index("idx_tab_payments_tab", "tab_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    tab_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    method: Mapped[PaymentMethod] = mapped_column(Enum(PaymentMethod, native_enum=False, length=20), nullable=False)
    status: Mapped[TabPaymentStatus] = mapped_column(Enum(TabPaymentStatus, native_enum=False, length=20), nullable=False)
    payer_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
