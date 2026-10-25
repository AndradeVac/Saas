"""Subscription plans: what each plan unlocks and how much of it.

The trial is the whole product for 14 days (no limits, every tool except white label). An expired trial keeps
the panel editable (so the owner stays invested) but stops taking new orders until a plan is chosen.

Limits are enforced here, in the API; the frontend only mirrors them to show locks and usage meters.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import PlanLimitError
from app.core.tenancy import get_tenant
from app.models.tenant import Tenant, TenantStatus

# Premium tools that can be locked per plan.
COUPONS = "coupons"
EXPORTS = "exports"
AUDIT = "audit"
WHITE_LABEL = "white_label"  # hides "Cardápio digital por Mesa Digital" on the customer menu
INSIGHTS = "insights"  # advanced analytics and the customers-to-win-back list
LOYALTY = "loyalty"  # digital loyalty card ("a cada 10 pedidos, 1 grátis")

FEATURE_NAMES = {
    COUPONS: "Cupons de desconto",
    EXPORTS: "Exportar relatórios (Excel, PDF e CSV)",
    AUDIT: "Auditoria de ações da equipe",
    WHITE_LABEL: "Cardápio sem a marca Mesa Digital",
    INSIGHTS: "Análises avançadas e clientes para reconquistar",
    LOYALTY: "Cartão fidelidade digital",
}


@dataclass(frozen=True)
class Plan:
    key: str
    name: str
    price: Decimal  # per month, BRL
    tagline: str
    max_products: int | None  # None = unlimited
    max_users: int | None
    max_orders: int | None  # total orders allowed while on this plan (only the trial is capped)
    features: frozenset[str] = field(default_factory=frozenset)
    highlight: bool = False
    public: bool = True  # listed on the pricing table


PLANS: dict[str, Plan] = {
    # The trial shows the whole product (a half-locked trial does not convince a real restaurant): no limits and
    # every tool for 14 days. Only the "Mesa Digital" badge stays on the menu while testing.
    "trial": Plan(
        key="trial", name="Degustação", price=Decimal("0"),
        tagline="14 dias com tudo liberado, sem cartão.",
        max_products=None, max_users=None, max_orders=None,
        features=frozenset({COUPONS, EXPORTS, AUDIT, INSIGHTS, LOYALTY}), public=False,
    ),
    "essencial": Plan(
        key="essencial", name="Essencial", price=Decimal("79.90"),
        tagline="Para quem está começando a vender pelo celular.",
        max_products=80, max_users=3, max_orders=None, features=frozenset({COUPONS, EXPORTS}),
    ),
    "pro": Plan(
        key="pro", name="Profissional", price=Decimal("149.90"),
        tagline="Controle total, equipe ilimitada e sua marca em primeiro lugar.",
        max_products=None, max_users=None, max_orders=None,
        features=frozenset({COUPONS, EXPORTS, AUDIT, WHITE_LABEL, INSIGHTS, LOYALTY}), highlight=True,
    ),
}
DEFAULT_PAID_PLAN = "pro"


def trial_expired(tenant: Tenant) -> bool:
    return (
        tenant.status is TenantStatus.TRIAL
        and tenant.trial_ends_at is not None
        and tenant.trial_ends_at <= datetime.now(timezone.utc)
    )


def plan_for(tenant: Tenant) -> Plan:
    """The plan whose rules apply right now. A tenant still in trial always gets the trial rules."""
    if tenant.status is TenantStatus.TRIAL:
        return PLANS["trial"]
    return PLANS.get(tenant.plan, PLANS[DEFAULT_PAID_PLAN])


def has_feature(tenant: Tenant, feature: str) -> bool:
    return feature in plan_for(tenant).features


def _upgrade_message(what: str) -> str:
    return f"{what} Assine um plano para liberar."


def require_feature(feature: str):
    """Route dependency: 402 when the tenant's plan does not include `feature`."""

    def dependency(tenant: Tenant = Depends(get_tenant)) -> Tenant:
        if not has_feature(tenant, feature):
            raise PlanLimitError(_upgrade_message(f"“{FEATURE_NAMES[feature]}” não está incluído no seu plano."), feature)
        return tenant

    return dependency


# ---- usage ----------------------------------------------------------------------------------

def count_products(db: Session, tenant_id: UUID) -> int:
    from app.models.product import Product

    return int(db.scalar(select(func.count(Product.id)).where(Product.tenant_id == tenant_id, Product.active.is_(True))) or 0)


def count_users(db: Session, tenant_id: UUID) -> int:
    from app.models.user import User

    return int(db.scalar(select(func.count(User.id)).where(User.tenant_id == tenant_id, User.active.is_(True))) or 0)


def count_orders(db: Session, tenant_id: UUID) -> int:
    """Orders that count toward the trial cap: cancelled ones never count (spam or mistakes must not use up the
    trial), and a table's bill (comanda) counts once however many rounds it had."""
    from app.models.order import Order, OrderStatus
    from app.models.tab import Tab, TabStatus

    standalone = db.scalar(
        select(func.count(Order.id)).where(
            Order.tenant_id == tenant_id, Order.tab_id.is_(None), Order.status != OrderStatus.CANCELLED
        )
    )
    tabs = db.scalar(select(func.count(Tab.id)).where(Tab.tenant_id == tenant_id, Tab.status != TabStatus.CANCELLED))
    return int(standalone or 0) + int(tabs or 0)


def can_take_orders(db: Session, tenant: Tenant) -> bool:
    from app.services.billing import billing_blocked

    if trial_expired(tenant) or billing_blocked(tenant):
        return False
    limit = plan_for(tenant).max_orders
    return limit is None or count_orders(db, tenant.id) < limit


def ensure_can_add_product(db: Session, tenant: Tenant) -> None:
    limit = plan_for(tenant).max_products
    if limit is not None and count_products(db, tenant.id) >= limit:
        raise PlanLimitError(_upgrade_message(f"Seu plano permite até {limit} produtos ativos."), "max_products")


def ensure_can_add_user(db: Session, tenant: Tenant) -> None:
    limit = plan_for(tenant).max_users
    if limit is not None and count_users(db, tenant.id) >= limit:
        users = "usuário" if limit == 1 else "usuários"
        raise PlanLimitError(_upgrade_message(f"Seu plano permite {limit} {users} na equipe."), "max_users")


def ensure_can_take_order(db: Session, tenant: Tenant) -> None:
    from app.services.billing import billing_blocked

    if trial_expired(tenant):
        raise PlanLimitError(_upgrade_message("Seu período de teste terminou."), "trial_expired")
    if billing_blocked(tenant):
        raise PlanLimitError("Sua assinatura está com pagamento pendente. Regularize em Meu plano para voltar a receber pedidos.", "billing_overdue")
    if not can_take_orders(db, tenant):
        limit = plan_for(tenant).max_orders
        raise PlanLimitError(_upgrade_message(f"Você usou os {limit} pedidos do período de teste."), "max_orders")



# ---- serialization ----------------------------------------------------------------------------

def plan_info(plan: Plan):
    from app.schemas.plan import PlanInfo

    return PlanInfo(
        key=plan.key, name=plan.name, price=plan.price, tagline=plan.tagline, max_products=plan.max_products,
        max_users=plan.max_users, max_orders=plan.max_orders, features=sorted(plan.features), highlight=plan.highlight,
    )


def plan_catalog():
    from app.core.config import settings
    from app.schemas.plan import PlanCatalog

    return PlanCatalog(
        plans=[plan_info(plan) for plan in PLANS.values()],
        feature_names=FEATURE_NAMES,
        trial_days=settings.trial_days,
        online_billing=bool(settings.asaas_api_key),
        annual_billing=settings.annual_billing,
        menu_import=bool(settings.anthropic_api_key),
        whatsapp_auto=bool(settings.whatsapp_token and settings.whatsapp_phone_number_id),
        sales_whatsapp="".join(ch for ch in settings.sales_whatsapp if ch.isdigit()),
    )


def plan_status(db: Session, tenant: Tenant):
    from app.schemas.plan import PlanUsage, TenantPlanStatus

    days_left = None
    if tenant.status is TenantStatus.TRIAL and tenant.trial_ends_at is not None:
        days_left = max(0, -(-int((tenant.trial_ends_at - datetime.now(timezone.utc)).total_seconds()) // 86_400))
    from app.services.billing import billing_blocked, grace_until

    return TenantPlanStatus(
        billing_status=tenant.billing_status,
        billing_plan=tenant.billing_plan,
        billing_cycle=tenant.billing_cycle,
        paid_until=tenant.paid_until,
        grace_until=grace_until(tenant),
        billing_blocked=billing_blocked(tenant),
        plan=plan_info(plan_for(tenant)),
        status=tenant.status.value,
        trial_ends_at=tenant.trial_ends_at,
        trial_days_left=days_left,
        trial_expired=trial_expired(tenant),
        can_take_orders=can_take_orders(db, tenant),
        usage=PlanUsage(
            products=count_products(db, tenant.id), users=count_users(db, tenant.id), orders=count_orders(db, tenant.id),
        ),
    )


def public_tenant(db: Session, tenant: Tenant):
    """What the customer menu sees: ordering also closes when the plan stops taking orders."""
    from app.schemas.tenant import PublicTenant

    data = PublicTenant.model_validate(tenant)
    data.is_open = data.is_open and can_take_orders(db, tenant)
    data.show_platform_badge = not has_feature(tenant, WHITE_LABEL)
    data.loyalty_enabled = tenant.loyalty_enabled and has_feature(tenant, LOYALTY)
    from app.services.customer_notify import whatsapp_enabled

    data.whatsapp_notifications = tenant.notify_customers and whatsapp_enabled()
    return data
