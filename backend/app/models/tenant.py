import enum
import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Enum, String, func, text
from sqlalchemy.dialects.postgresql import UUID
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
    # When off, the public menu is visible but customers cannot place orders.
    accepting_orders: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    # Last order number handed out; incremented atomically so numbers are sequential per tenant.
    order_counter: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
