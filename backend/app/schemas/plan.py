from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class PlanInfo(BaseModel):
    key: str
    name: str
    price: Decimal
    tagline: str
    max_products: int | None
    max_users: int | None
    max_orders: int | None
    features: list[str]
    highlight: bool


class PlanCatalog(BaseModel):
    plans: list[PlanInfo]
    # Feature key -> label, so every screen names locked tools the same way.
    feature_names: dict[str, str]
    trial_days: int
    # WhatsApp number (digits) of the platform's sales team; empty when not configured.
    sales_whatsapp: str


class PlanUsage(BaseModel):
    products: int
    users: int
    orders: int


class TenantPlanStatus(BaseModel):
    plan: PlanInfo
    status: str
    trial_ends_at: datetime | None
    trial_days_left: int | None
    trial_expired: bool
    can_take_orders: bool
    usage: PlanUsage
