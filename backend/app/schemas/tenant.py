import re
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.core.hours import DAYS
from app.core.tenancy import RESERVED_SLUGS, SLUG_PATTERN, normalize_slug
from app.models.order import PaymentMethod, ServiceType
from app.models.tenant import BusinessType, TenantStatus
from app.schemas.common import safe_image_url

_COLOR_PATTERN = re.compile(r"^#[0-9a-fA-F]{6}$")
_TIME_PATTERN = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def validate_slug(value: str) -> str:
    slug = normalize_slug(value)
    if not SLUG_PATTERN.match(slug):
        raise ValueError("O endereço deve ter de 3 a 40 caracteres: letras minúsculas, números e hífen.")
    if "--" in slug:
        raise ValueError("O endereço não pode ter dois hífens seguidos.")
    if slug in RESERVED_SLUGS:
        raise ValueError("Este endereço é reservado. Escolha outro.")
    return slug


class SignupRequest(BaseModel):
    business_name: str = Field(min_length=2, max_length=120)
    business_type: BusinessType = BusinessType.RESTAURANT
    slug: str = Field(min_length=3, max_length=40)
    phone: str | None = Field(default=None, max_length=30)
    admin_name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

    @field_validator("slug")
    @classmethod
    def _validate_slug(cls, value: str) -> str:
        return validate_slug(value)

    @field_validator("business_name", "admin_name")
    @classmethod
    def _collapse_spaces(cls, value: str) -> str:
        return " ".join(value.split())


class SignupResponse(BaseModel):
    slug: str
    name: str
    url: str
    login_url: str


class SlugAvailability(BaseModel):
    slug: str
    available: bool
    reason: str | None = None


class PublicTenant(BaseModel):
    """What anyone visiting <slug>.<domain> may know about the business."""

    model_config = ConfigDict(from_attributes=True)

    slug: str
    name: str
    business_type: BusinessType
    description: str | None
    phone: str | None
    address: str | None
    instagram: str | None
    logo_url: str | None
    cover_url: str | None
    primary_color: str
    pix_key: str | None
    accepting_orders: bool
    # accepting_orders AND inside the opening hours (when hours are enforced).
    is_open: bool
    hours_mode: str
    opening_hours: dict[str, list[list[str]]]
    enabled_services: list[ServiceType]
    accepted_payments: list[PaymentMethod]
    delivery_fee: Decimal
    min_order_value: Decimal
    service_fee_percent: Decimal


class TenantSettingsResponse(PublicTenant):
    id: UUID
    timezone: str
    status: TenantStatus
    plan: str
    trial_ends_at: datetime | None
    created_at: datetime


class TenantSettingsUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    business_type: BusinessType | None = None
    description: str | None = Field(default=None, max_length=500)
    phone: str | None = Field(default=None, max_length=30)
    address: str | None = Field(default=None, max_length=200)
    instagram: str | None = Field(default=None, max_length=60)
    logo_url: str | None = Field(default=None, max_length=300)
    cover_url: str | None = Field(default=None, max_length=300)
    primary_color: str | None = None
    pix_key: str | None = Field(default=None, max_length=100)
    accepting_orders: bool | None = None
    hours_mode: str | None = Field(default=None, pattern="^(MANUAL|SCHEDULE)$")
    opening_hours: dict[str, list[list[str]]] | None = None
    enabled_services: list[ServiceType] | None = Field(default=None, min_length=1)
    accepted_payments: list[PaymentMethod] | None = Field(default=None, min_length=1)
    delivery_fee: Decimal | None = Field(default=None, ge=0, le=1000, max_digits=10, decimal_places=2)
    min_order_value: Decimal | None = Field(default=None, ge=0, le=100000, max_digits=10, decimal_places=2)
    service_fee_percent: Decimal | None = Field(default=None, ge=0, le=30, max_digits=5, decimal_places=2)
    timezone: str | None = Field(default=None, max_length=60)

    @field_validator("logo_url", "cover_url")
    @classmethod
    def _validate_images(cls, value: str | None) -> str | None:
        return safe_image_url(value)

    @field_validator("primary_color")
    @classmethod
    def _validate_color(cls, value: str | None) -> str | None:
        if value is not None and not _COLOR_PATTERN.match(value):
            raise ValueError("Informe a cor no formato #RRGGBB.")
        return value.lower() if value else value

    @field_validator("opening_hours")
    @classmethod
    def _validate_hours(cls, value: dict | None) -> dict | None:
        if value is None:
            return None
        cleaned: dict[str, list[list[str]]] = {}
        for day, intervals in value.items():
            if day not in DAYS:
                raise ValueError("Dia da semana inválido.")
            if len(intervals) > 4:
                raise ValueError("Use no máximo 4 intervalos por dia.")
            for interval in intervals:
                if len(interval) != 2 or not all(_TIME_PATTERN.match(t) for t in interval):
                    raise ValueError("Horários devem estar no formato HH:MM.")
            if intervals:
                cleaned[day] = [list(i) for i in intervals]
        return cleaned

    @field_validator("timezone")
    @classmethod
    def _validate_timezone(cls, value: str | None) -> str | None:
        if value is None:
            return None
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as error:
            raise ValueError("Fuso horário inválido.") from error
        return value
