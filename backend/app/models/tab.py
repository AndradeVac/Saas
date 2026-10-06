import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, SmallInteger, String, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.order import PaymentMethod


class TabStatus(str, enum.Enum):
    PENDING = "PENDING"  # first order arrived; waiting for staff to confirm the table is real
    OPEN = "OPEN"  # taking orders
    CLOSING = "CLOSING"  # customer asked for the bill
    CLOSED = "CLOSED"  # paid
    CANCELLED = "CANCELLED"


ACTIVE_TAB_STATUSES = (TabStatus.PENDING, TabStatus.OPEN, TabStatus.CLOSING)


class Tab(Base):
    """A table's open bill (comanda): every dine-in order of that table points here and is paid at the end."""

    __tablename__ = "tabs"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_tabs_tenant_id"),
        UniqueConstraint("tenant_id", "number", name="uq_tabs_tenant_number"),
        # At most one active bill per table; also settles races between two phones ordering at once.
        Index(
            "uq_tabs_active_table", "tenant_id", "table_label", unique=True,
            postgresql_where=text("status IN ('PENDING', 'OPEN', 'CLOSING')"),
        ),
        Index("idx_tabs_tenant_status", "tenant_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    # Lets every phone at the table follow the bill without logging in.
    public_token: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), default=uuid.uuid4, nullable=False, unique=True)
    table_label: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[TabStatus] = mapped_column(Enum(TabStatus, native_enum=False, length=20), nullable=False, default=TabStatus.PENDING)
    opened_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    # What the customer chose when asking for the bill, and how many people will split it (informative).
    requested_payment_method: Mapped[PaymentMethod | None] = mapped_column(Enum(PaymentMethod, native_enum=False, length=20), nullable=True)
    split_count: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    payment_method: Mapped[PaymentMethod | None] = mapped_column(Enum(PaymentMethod, native_enum=False, length=20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_order_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    close_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    orders: Mapped[list["Order"]] = relationship(
        "Order", primaryjoin="Tab.id == foreign(Order.tab_id)", back_populates="tab", order_by="Order.created_at"
    )
