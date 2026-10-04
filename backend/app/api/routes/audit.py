from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import admin_only
from app.models.audit_log import AuditLog
from app.models.user import User
from app.schemas.audit import AuditLogResponse
from app.schemas.common import Page

router = APIRouter(prefix="/audit", tags=["Audit"])


@router.get("", response_model=Page[AuditLogResponse])
def get_audit_logs(
    entity_type: str | None = Query(default=None, max_length=80),
    page: int = Query(default=1, ge=1, le=10_000),
    page_size: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    actor: User = Depends(admin_only),
):
    conditions = [AuditLog.tenant_id == actor.tenant_id]
    if entity_type:
        conditions.append(AuditLog.entity_type == entity_type)
    total = int(db.scalar(select(func.count(AuditLog.id)).where(*conditions)) or 0)
    rows = db.execute(
        select(AuditLog, User.name)
        .outerjoin(User, User.id == AuditLog.actor_user_id)
        .where(*conditions)
        .order_by(desc(AuditLog.created_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    items = [
        AuditLogResponse(
            id=log.id, actor_name=name, action=log.action, entity_type=log.entity_type,
            entity_id=log.entity_id, details=log.details, created_at=log.created_at,
        )
        for log, name in rows
    ]
    return Page(items=items, total=total, page=page, page_size=page_size)
