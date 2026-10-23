from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.exceptions import BusinessRuleError
from app.core.security import staff_only
from app.models.user import User
from app.services import push

router = APIRouter(prefix="/push", tags=["Push"])


class SubscriptionKeys(BaseModel):
    p256dh: str = Field(max_length=200)
    auth: str = Field(max_length=100)


class SubscriptionIn(BaseModel):
    endpoint: str = Field(min_length=10, max_length=1000)
    keys: SubscriptionKeys


class Unsubscribe(BaseModel):
    endpoint: str = Field(max_length=1000)


@router.get("/public-key")
def public_key():
    return {"key": settings.vapid_public_key if push.enabled() else None}


@router.post("/subscribe", status_code=status.HTTP_204_NO_CONTENT)
def subscribe(data: SubscriptionIn, db: Session = Depends(get_db), actor: User = Depends(staff_only)):
    if not push.enabled():
        raise BusinessRuleError("Notificações ainda não estão disponíveis.")
    if not data.endpoint.startswith("https://"):
        raise BusinessRuleError("Inscrição inválida.")
    push.subscribe(db, actor.tenant_id, actor.id, data.endpoint, data.keys.p256dh, data.keys.auth)


@router.post("/unsubscribe", status_code=status.HTTP_204_NO_CONTENT)
def unsubscribe(data: Unsubscribe, db: Session = Depends(get_db), actor: User = Depends(staff_only)):
    push.unsubscribe(db, actor.id, data.endpoint)
