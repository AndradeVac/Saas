"""Access records required by the Marco Civil da Internet (art. 15): who connected from which IP, and when."""
import logging
from uuid import UUID

from fastapi import Request
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.client_ip import client_ip
from app.models.access_log import AccessLog

logger = logging.getLogger(__name__)
RETENTION_DAYS = 190  # the law asks for 6 months; a few days of margin, then it is deleted (LGPD: no longer than needed)


def record_access(db: Session, request: Request, event: str, tenant_id: UUID | None, user_id: UUID | None = None, reference: str | None = None) -> None:
    """Best effort: a failure here must never block a login or an order."""
    try:
        db.add(AccessLog(tenant_id=tenant_id, user_id=user_id, event=event, reference=reference, ip=client_ip(request)[:45]))
        db.commit()
    except Exception:
        db.rollback()
        logger.warning("Could not record the access log", exc_info=True)


def purge_old_access_logs() -> None:
    from app.core.database import SessionLocal

    with SessionLocal() as db:
        db.execute(text("DELETE FROM access_logs WHERE created_at < now() - make_interval(days => :days)"), {"days": RETENTION_DAYS})
        db.commit()
