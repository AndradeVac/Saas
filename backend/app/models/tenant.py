import enum
import uuid
from datetime import datetime

from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, DateTime, Enum, Numeric, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class BusinessType(str, enum.Enum):
    RESTAURANT = "RESTAURANT"
    BAKERY = "BAKERY"
    CAFE = "CAFE"
    SNACK_BAR = "SNACK_BAR"
    PIZZERIA = "PIZZERIA"
    OTHER = "OTHER"


class TenantStatus(str, enum.Enum):
    TRIAL = "TRIAL"
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"


class Tenant(Base):
    """One customer of the platform (a restaurant, bakery, café...). Every other table points here."""

    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    # Subdomain: <slug>.<root domain>. Lowercase letters, digits and hyphens only.
    slug: Mapped[str] = mapped_column(String(40), nullable=False, unique=True, name="slug")
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    business_type: Mapped[BusinessType] = mapped_column(
        Enum(BusinessType, native_enum=False, length=20), nullable=False, default=BusinessType.RESTAURANT
    )
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    logo_url: Mapped[str | None] = mapped_column(String(300), nullable=True)
    primary_color: Mapped[str] = mapped_column(String(7), nullable=False, default="#c2410c", server_default="#c2410c")
    timezone: Mapped[str] = mapped_column(
        String(60), nullable=False, default="America/Sao_Paulo", server_default="America/Sao_Paulo"
    )
    status: Mapped[TenantStatus] = mapped_column(
        Enum(TenantStatus, native_enum=False, length=20), nullable=False, default=TenantStatus.TRIAL
    )
    plan: Mapped[str] = mapped_column(String(30), nullable=False, default="trial", server_default="trial")
    trial_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    address: Mapped[str | None] = mapped_column(String(200), nullable=True)
    instagram: Mapped[str | None] = mapped_column(String(60), nullable=True)
    cover_url: Mapped[str | None] = mapped_column(String(300), nullable=True)
    pix_key: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # MANUAL: `accepting_orders` alone decides. SCHEDULE: also requires being inside `opening_hours`.
    hours_mode: Mapped[str] = mapped_column(String(10), nullable=False, default="MANUAL", server_default="MANUAL")
    # {"mon": [["08:00", "18:00"]], ...} in the tenant's time zone; a close earlier than the open crosses midnight.
    opening_hours: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    enabled_services: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=lambda: ["DINE_IN", "TAKEAWAY"], server_default=text("""'["DINE_IN","TAKEAWAY"]'::jsonb""")
    )
    accepted_payments: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=lambda: ["CASH", "PIX", "CARD"], server_default=text("""'["CASH","PIX","CARD"]'::jsonb""")
    )
    delivery_fee: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=0, server_default="0")
    min_order_value: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=0, server_default="0")
    # Percentage added to dine-in orders (taxa de serviço).
    service_fee_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=0, server_default="0")
    # When off, the public menu is visible but customers cannot place orders.
    accepting_orders: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    # Last order number handed out; incremented atomically so numbers are sequential per tenant.
    order_counter: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    @property
    def is_open(self) -> bool:
        """Whether customers can place orders right now (switch + opening hours)."""
        from app.core.hours import is_open_now

        return is_open_now(
            accepting_orders=self.accepting_orders,
            hours_mode=self.hours_mode,
            opening_hours=self.opening_hours or {},
            timezone=self.timezone,
        )
