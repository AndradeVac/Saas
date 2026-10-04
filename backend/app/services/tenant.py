from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import BusinessRuleError
from app.core.tenancy import RESERVED_SLUGS
from app.models.category import Category
from app.models.tenant import BusinessType, Tenant, TenantStatus
from app.models.user import User, UserRole
from app.repositories.tenant import TenantRepository
from app.schemas.tenant import SignupRequest, SlugAvailability, TenantSettingsUpdate
from app.services.audit import record_audit
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


class TenantService:
    def __init__(self, db: Session):
        self.repository = TenantRepository(db)
        self.db = db

    def check_slug(self, slug: str) -> SlugAvailability:
        from app.schemas.tenant import validate_slug

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
        for field in ("name", "business_type", "primary_color", "accepting_orders"):
            value = getattr(data, field)
            if value is not None:
                setattr(tenant, field, value)
        # These can be cleared by sending null explicitly.
        for field in ("phone", "logo_url"):
            if field in data.model_fields_set:
                setattr(tenant, field, getattr(data, field) or None)

        record_audit(self.db, tenant.id, actor, "TENANT_SETTINGS_UPDATED", "TENANT", tenant.id)
        self.repository.update(tenant)
        self.db.commit()
        return tenant
