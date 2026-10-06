import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class OrderStatus(str, enum.Enum):
    RECEIVED = "RECEIVED"
    PREPARING = "PREPARING"
    READY = "READY"
    FINISHED = "FINISHED"
    CANCELLED = "CANCELLED"


class ServiceType(str, enum.Enum):
    DINE_IN = "DINE_IN"
    TAKEAWAY = "TAKEAWAY"
    DELIVERY = "DELIVERY"


class PaymentMethod(str, enum.Enum):
    PIX = "PIX"
    CARD = "CARD"
    CASH = "CASH"
    # Dine-in order on an open bill (comanda): the real method is set when the bill is closed.
    TAB = "TAB"


class PaymentStatus(str, enum.Enum):
    PENDING = "PENDING"
    PAID = "PAID"


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
        CheckConstraint("subtotal >= 0", name="chk_orders_subtotal"),
        CheckConstraint("total >= 0", name="chk_orders_total"),
        UniqueConstraint("tenant_id", "order_number", name="uq_orders_tenant_number"),
        Index("idx_orders_tenant_created_at", "tenant_id", "created_at"),
        Index("idx_orders_customer_id", "customer_id"),
        Index("idx_orders_tenant_status", "tenant_id", "status"),
        # An order can only point at a customer of the same tenant.
        ForeignKeyConstraint(["tenant_id", "customer_id"], ["customers.tenant_id", "customers.id"], name="fk_orders_tenant_customer"),
        ForeignKeyConstraint(["tenant_id", "tab_id"], ["tabs.tenant_id", "tabs.id"], name="fk_orders_tenant_tab"),
        Index("idx_orders_tab_id", "tab_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    # Sequential per tenant (the number the kitchen calls out), see TenantRepository.next_order_number.
    order_number: Mapped[int] = mapped_column(Integer, nullable=False)
    # Unguessable id handed to the customer to follow the order without logging in.
    public_token: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), default=uuid.uuid4, nullable=False, unique=True)
    customer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus, native_enum=False, length=20), nullable=False, default=OrderStatus.RECEIVED
    )
    service_type: Mapped[ServiceType] = mapped_column(
        Enum(ServiceType, native_enum=False, length=20), nullable=False, default=ServiceType.DINE_IN
    )
    # Table / tab identifier typed by the customer or staff ("12", "Balcão"...).
    delivery_address: Mapped[str | None] = mapped_column(String(300), nullable=True)
    coupon_code: Mapped[str | None] = mapped_column(String(40), nullable=True)
    table_label: Mapped[str | None] = mapped_column(String(30), nullable=True)
    tab_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    payment_method: Mapped[PaymentMethod] = mapped_column(
        Enum(PaymentMethod, native_enum=False, length=20), nullable=False
    )
    payment_status: Mapped[PaymentStatus] = mapped_column(
        Enum(PaymentStatus, native_enum=False, length=20), nullable=False, default=PaymentStatus.PENDING
    )
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    delivery_fee: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=0, server_default="0")
    service_fee: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=0, server_default="0")
    discount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=0, server_default="0")
    total: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    customer: Mapped["Customer"] = relationship("Customer", back_populates="orders")
    # Joined on tab_id alone: tenant_id is already owned by the customer relationship.
    tab: Mapped["Tab | None"] = relationship("Tab", primaryjoin="foreign(Order.tab_id) == Tab.id", back_populates="orders")
    items: Mapped[list["OrderItem"]] = relationship("OrderItem", back_populates="order")
    status_history: Mapped[list["OrderStatusHistory"]] = relationship(
        "OrderStatusHistory", back_populates="order", order_by="OrderStatusHistory.created_at"
    )

    @property
    def customer_name(self) -> str | None:
        return self.customer.name if self.customer is not None else None

    @property
    def customer_phone(self) -> str | None:
        return self.customer.phone if self.customer is not None else None
