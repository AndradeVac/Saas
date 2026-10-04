from uuid import UUID

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.user import User


def record_audit(
    db: Session,
    tenant_id: UUID,
    actor: User | None,
    action: str,
    entity_type: str,
    entity_id: UUID | None = None,
    details: str | None = None,
) -> None:
    """Adds an audit entry to the current transaction (the caller commits)."""
    db.add(AuditLog(
        tenant_id=tenant_id,
        actor_user_id=actor.id if actor else None,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details,
    ))
