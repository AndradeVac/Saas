from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import BusinessRuleError
from app.core.tenancy import RESERVED_SLUGS
from app.models.category import Category
from app.models.tenant import BusinessType, Tenant, TenantStatus
from app.models.user import User, UserRole
from app.repositories.tenant import TenantRepository
from app.schemas.tenant import SignupRequest, SlugAvailability, TenantSettingsUpdate, validate_slug
from app.services.audit import record_audit
from app.services.media import MediaService
from app.services.user import UserService

# Starter menu sections created with a new account, so the owner can start adding products right away.
STARTER_CATEGORIES: dict[BusinessType, list[str]] = {
    BusinessType.RESTAURANT: ["Entradas", "Pratos principais", "Sobremesas", "Bebidas"],
    BusinessType.BAKERY: ["Pães", "Doces e bolos", "Salgados", "Bebidas"],
    BusinessType.CAFE: ["Cafés", "Bebidas geladas", "Lanches", "Doces"],
    BusinessType.SNACK_BAR: ["Lanches", "Porções", "Bebidas", "Sobremesas"],
    BusinessType.PIZZERIA: ["Pizzas salgadas", "Pizzas doces", "Bebidas", "Sobremesas"],
    BusinessType.OTHER: ["Cardápio", "Bebidas"],
}

TAB_BUSINESSES = {BusinessType.RESTAURANT, BusinessType.SNACK_BAR, BusinessType.PIZZERIA, BusinessType.CAFE}

_PLAIN_FIELDS = (
    "name", "business_type", "primary_color", "accepting_orders", "hours_mode", "opening_hours",
    "enabled_services", "accepted_payments", "delivery_fee", "min_order_value", "service_fee_percent", "timezone",
    "tabs_enabled", "tabs_auto_approve", "tab_idle_minutes",
)
# Can be cleared by sending null explicitly.
_NULLABLE_FIELDS = ("description", "phone", "address", "instagram", "pix_key", "logo_url", "cover_url")


class TenantService:
    def __init__(self, db: Session):
        self.repository = TenantRepository(db)
        self.db = db

    def check_slug(self, slug: str) -> SlugAvailability:
        try:
            slug = validate_slug(slug)
        except ValueError as error:
            return SlugAvailability(slug=slug, available=False, reason=str(error))
        if slug in RESERVED_SLUGS or self.repository.slug_exists(slug):
            return SlugAvailability(slug=slug, available=False, reason="Este endereço já está em uso.")
        return SlugAvailability(slug=slug, available=True)

    def signup(self, data: SignupRequest) -> Tenant:
        if self.repository.slug_exists(data.slug):
            raise BusinessRuleError("Este endereço já está em uso. Escolha outro.")

        tenant = Tenant(
            slug=data.slug,
            name=data.business_name,
            business_type=data.business_type,
            phone=data.phone,
            status=TenantStatus.TRIAL,
            plan="trial",
            trial_ends_at=datetime.now(timezone.utc) + timedelta(days=settings.trial_days),
            # Table service businesses start with the open bill per table (comanda); counters keep paying per order.
            tabs_enabled=data.business_type in TAB_BUSINESSES,
        )
        try:
            self.repository.create(tenant)

            owner = User(
                tenant_id=tenant.id,
                name=data.admin_name,
                email=str(data.email).strip().lower(),
                password_hash=UserService.password_hash.hash(data.password),
                role=UserRole.ADMIN,
            )
            self.db.add(owner)
            self.db.flush()

            for position, name in enumerate(STARTER_CATEGORIES[data.business_type]):
                self.db.add(Category(tenant_id=tenant.id, name=name, sort_order=position))
            record_audit(self.db, tenant.id, owner, "TENANT_CREATED", "TENANT", tenant.id, tenant.slug)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return tenant

    def update_settings(self, tenant: Tenant, data: TenantSettingsUpdate, actor: User) -> Tenant:
        media = MediaService(self.db, tenant.id)
        replaced_images = []

        for field in _PLAIN_FIELDS:
            if field in data.model_fields_set and getattr(data, field) is not None:
                setattr(tenant, field, getattr(data, field))
        for field in _NULLABLE_FIELDS:
            if field in data.model_fields_set:
                if field in ("logo_url", "cover_url") and getattr(tenant, field) != getattr(data, field):
                    replaced_images.append(getattr(tenant, field))
                setattr(tenant, field, getattr(data, field) or None)

        if tenant.hours_mode == "SCHEDULE" and not tenant.opening_hours:
            raise BusinessRuleError("Cadastre ao menos um horário de funcionamento ou use o modo manual.")

        self.repository.update(tenant)
        for url in replaced_images:
            media.release_if_orphan(url)
        record_audit(self.db, tenant.id, actor, "TENANT_SETTINGS_UPDATED", "TENANT", tenant.id)
        self.db.commit()
        return tenant
