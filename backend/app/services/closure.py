"""Account closure (Termos de Uso, seção 3 e 8; LGPD art. 16: data is deleted when the relationship ends).

- The owner closes the store in Settings (password + typing the address). It goes offline at once.
- 60 days without paying closes it automatically, after a warning e-mail 10 days before.
- PURGE_AFTER_DAYS after the closure, everything is deleted (the tenant row cascades to every table) and so are its
  images in object storage. Until then the platform can reactivate it (scripts.manage_tenant activate), and a late
  payment brings it back too. Daily backups age out 30 days later; access records stay 6 months (Marco Civil).
"""
from __future__ import annotations

import html
import logging
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core import asaas, storage
from app.core.config import settings
from app.core.database import SessionLocal
from app.core.email import send_email
from app.models.media import Media
from app.models.tenant import Tenant, TenantStatus
from app.models.user import User
from app.services.audit import record_audit
from app.services.lifecycle import _layout, _owner_email, send_once

logger = logging.getLogger(__name__)

PURGE_AFTER_DAYS = 30
UNPAID_CLOSE_DAYS = 60
UNPAID_WARNING_DAYS = 50


def _demo_slugs() -> set[str]:
    return {slug.strip() for slug in settings.demo_slugs.split(",") if slug.strip()}


def purge_date(tenant: Tenant) -> date | None:
    return (tenant.closed_at + timedelta(days=PURGE_AFTER_DAYS)).date() if tenant.closed_at else None


def close_tenant(db: Session, tenant: Tenant, reason: str, actor: User | None) -> None:
    """Takes the store offline, stops the subscription and schedules the purge. Sends the confirmation e-mail."""
    recipient = _owner_email(db, tenant)  # read before: after this the store is suspended
    if tenant.billing_subscription_id and tenant.billing_status in ("PENDING", "ACTIVE", "OVERDUE") and asaas.enabled():
        try:
            asaas.delete_subscription(tenant.billing_subscription_id)
        except Exception:  # the closure must not depend on Asaas; the platform cancels it by hand if this fails
            logger.exception("Could not cancel the Asaas subscription of %s", tenant.slug)
    if tenant.billing_status in ("PENDING", "ACTIVE", "OVERDUE", "COURTESY"):
        tenant.billing_status = "CANCELED"
    tenant.status, tenant.accepting_orders = TenantStatus.SUSPENDED, False
    tenant.closed_at, tenant.closure_reason = datetime.now(timezone.utc), reason
    record_audit(db, tenant.id, actor, "ACCOUNT_CLOSED", "TENANT", tenant.id, f"{reason}; dados apagados em {purge_date(tenant):%d/%m/%Y}")
    db.commit()
    if recipient:
        email, name = recipient
        when = f"{purge_date(tenant):%d/%m/%Y}"
        why = ("Recebemos o seu pedido de encerramento." if reason == "REQUEST"
               else f"A assinatura ficou {UNPAID_CLOSE_DAYS} dias sem pagamento, então a conta foi encerrada, como previsto nos Termos de Uso.")
        page, text = _layout(tenant, f"{name}, sua conta foi encerrada", [
            f"{why} O cardápio <strong>{html.escape(tenant.name.strip())}</strong> saiu do ar e não recebe mais pedidos. Nenhuma cobrança nova será feita.",
            f"Os dados da loja (cardápio, pedidos, clientes e equipe) ficam guardados até <strong>{when}</strong> e depois são apagados de forma definitiva.",
            "Mudou de ideia ou precisa de uma cópia dos dados? Responda este e-mail antes dessa data.",
        ], "Falar com o suporte", f"mailto:contato@{settings.root_domain}")
        send_email(email, f"Sua conta no Mesa Digital foi encerrada (dados até {when})", page, text)


def purge_tenant(db: Session, tenant: Tenant) -> None:
    """Deletes the store for good: images in the bucket first, then the row (ON DELETE CASCADE does the rest)."""
    keys = list(db.scalars(select(Media.storage_key).where(Media.tenant_id == tenant.id, Media.storage_key.is_not(None))))
    for key in keys:
        try:
            storage.delete_object(key)
        except Exception:  # a leftover file only costs storage; the personal data is in the database
            logger.warning("Could not delete %s from object storage", key, exc_info=True)
    slug = tenant.slug
    db.execute(delete(Tenant).where(Tenant.id == tenant.id))  # the database cascade, not the ORM, removes the children
    db.commit()
    logger.info("Purged closed account %s (%d images)", slug, len(keys))


def run(now: datetime | None = None) -> dict[str, int]:
    """Hourly: warns and closes unpaid accounts, and purges accounts closed more than PURGE_AFTER_DAYS ago."""
    now = now or datetime.now(timezone.utc)
    today = now.date()
    demos = _demo_slugs()
    done = {"warned": 0, "closed": 0, "purged": 0}
    with SessionLocal() as db:
        unpaid = db.scalars(select(Tenant).where(
            Tenant.billing_status == "OVERDUE", Tenant.past_due_since.is_not(None), Tenant.status != TenantStatus.SUSPENDED,
        )).all()
        for tenant in unpaid:
            if tenant.slug in demos:
                continue
            days = (today - tenant.past_due_since).days
            try:
                if days >= UNPAID_CLOSE_DAYS:
                    close_tenant(db, tenant, "UNPAID", None)
                    done["closed"] += 1
                elif days >= UNPAID_WARNING_DAYS:
                    close_on = tenant.past_due_since + timedelta(days=UNPAID_CLOSE_DAYS)
                    done["warned"] += send_once(db, tenant, "closing_unpaid", tenant.past_due_since.isoformat(),
                        "{nome}, sua conta será encerrada em " + f"{close_on:%d/%m/%Y}", [
                            f"A assinatura está sem pagamento há {days} dias. Pelos Termos de Uso, a conta é encerrada com {UNPAID_CLOSE_DAYS} dias e os dados são apagados {PURGE_AFTER_DAYS} dias depois.",
                            "Para manter tudo (cardápio, pedidos e clientes), é só pagar a cobrança em aberto pelo painel.",
                        ], "Pagar agora", "/painel/plano")
            except Exception:
                db.rollback()
                logger.exception("Closure check failed for %s", tenant.slug)

        limit = now - timedelta(days=PURGE_AFTER_DAYS)
        expired = db.scalars(select(Tenant).where(
            Tenant.status == TenantStatus.SUSPENDED, Tenant.closed_at.is_not(None), Tenant.closed_at < limit,
        )).all()
        for tenant in expired:
            if tenant.slug in demos:
                continue
            try:
                purge_tenant(db, tenant)
                done["purged"] += 1
            except Exception:
                db.rollback()
                logger.exception("Purge failed for %s", tenant.slug)
    return done
