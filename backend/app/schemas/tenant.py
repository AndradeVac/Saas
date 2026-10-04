import re
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.core.tenancy import RESERVED_SLUGS, SLUG_PATTERN, normalize_slug
from app.models.tenant import BusinessType, TenantStatus

_COLOR_PATTERN = re.compile(r"^#[0-9a-fA-F]{6}$")


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
    phone: str | None
    logo_url: str | None
    primary_color: str
    accepting_orders: bool


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
    phone: str | None = Field(default=None, max_length=30)
    logo_url: str | None = Field(default=None, max_length=300)
    primary_color: str | None = None
    accepting_orders: bool | None = None

    @field_validator("primary_color")
    @classmethod
    def _validate_color(cls, value: str | None) -> str | None:
        if value is not None and not _COLOR_PATTERN.match(value):
            raise ValueError("Informe a cor no formato #RRGGBB.")
        return value.lower() if value else value
