from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class AuditLogResponse(BaseModel):
    id: UUID
    actor_name: str | None
    action: str
    entity_type: str
    entity_id: UUID | None
    details: str | None
    created_at: datetime
