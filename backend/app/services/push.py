"""Web Push: "Novo pedido #123" on the staff's phones and computers, even with the panel closed."""
from __future__ import annotations

import json
import logging
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.push_subscription import PushSubscription

logger = logging.getLogger(__name__)


def enabled() -> bool:
    return bool(settings.vapid_public_key and settings.vapid_private_key)


def subscribe(db: Session, tenant_id: UUID, user_id: UUID, endpoint: str, p256dh: str, auth: str) -> None:
    existing = db.scalar(select(PushSubscription).where(PushSubscription.endpoint == endpoint))
    if existing is None:
        db.add(PushSubscription(tenant_id=tenant_id, user_id=user_id, endpoint=endpoint, p256dh=p256dh, auth=auth))
    else:  # the same browser, now logged into this store / user
        existing.tenant_id, existing.user_id, existing.p256dh, existing.auth = tenant_id, user_id, p256dh, auth
    db.commit()


def unsubscribe(db: Session, user_id: UUID, endpoint: str) -> None:
    db.execute(delete(PushSubscription).where(PushSubscription.endpoint == endpoint, PushSubscription.user_id == user_id))
    db.commit()


def notify_tenant(tenant_id: UUID, title: str, body: str, url: str = "/painel/pedidos") -> None:
    """Runs after the response (background task): a slow push service never delays the customer's order."""
    if not enabled():
        return
    from pywebpush import WebPushException, webpush

    payload = json.dumps({"title": title, "body": body, "url": url, "tag": "novo-pedido"})
    with SessionLocal() as db:
        subscriptions = list(db.scalars(select(PushSubscription).where(PushSubscription.tenant_id == tenant_id)))
        gone = []
        for sub in subscriptions:
            try:
                webpush(
                    subscription_info={"endpoint": sub.endpoint, "keys": {"p256dh": sub.p256dh, "auth": sub.auth}},
                    data=payload, vapid_private_key=settings.vapid_private_key,
                    vapid_claims={"sub": settings.vapid_subject}, ttl=600, timeout=8,
                )
            except WebPushException as error:
                status = getattr(error.response, "status_code", None)
                if status in (404, 410):  # the browser dropped the subscription
                    gone.append(sub.id)
                else:
                    logger.warning("Web push failed (%s)", status)
            except Exception:
                logger.warning("Web push failed", exc_info=True)
        if gone:
            db.execute(delete(PushSubscription).where(PushSubscription.id.in_(gone)))
            db.commit()
