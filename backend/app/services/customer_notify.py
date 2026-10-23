"""Automatic messages to the customer when the order moves: "em preparo" and "pronto" (or "saiu para entrega").

Two channels, both optional: WhatsApp through Meta's official Cloud API (templates approved in Meta; the platform's
number sends on behalf of each store) and a notification on the customer's phone (web push from the order screen).
Runs after the response, so a slow channel never delays the kitchen.
"""
from __future__ import annotations

import json
import logging
import re
import urllib.request
from uuid import UUID

from sqlalchemy import delete, select

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.customer import Customer
from app.models.order import Order, OrderStatus, ServiceType
from app.models.push_subscription import OrderPushSubscription
from app.models.tenant import Tenant

logger = logging.getLogger(__name__)


def whatsapp_enabled() -> bool:
    return bool(settings.whatsapp_token and settings.whatsapp_phone_number_id)


def ready_hint(order: Order) -> str:
    if order.service_type is ServiceType.DELIVERY:
        return "Ele já está saindo para entrega."
    if order.service_type is ServiceType.DINE_IN:
        return f"Já vai para a mesa {order.table_label}." if order.table_label else "Já vai para a sua mesa."
    return "Pode retirar no balcão."


def message(order: Order, tenant: Tenant, status: OrderStatus) -> tuple[str, str] | None:
    """(title, body) for the statuses worth telling the customer about."""
    store = tenant.name.strip()
    if status is OrderStatus.PREPARING:
        return f"Pedido #{order.order_number} em preparo", f"{store} já está preparando o seu pedido."
    if status is OrderStatus.READY:
        return f"Pedido #{order.order_number} pronto!", f"{store}: seu pedido está pronto. {ready_hint(order)}"
    return None


def _whatsapp_number(phone: str | None) -> str | None:
    digits = re.sub(r"\D", "", phone or "")
    if len(digits) in (10, 11):
        return "55" + digits
    return digits if len(digits) in (12, 13) and digits.startswith("55") else None


def send_whatsapp(to: str, template: str, params: list[str]) -> bool:
    body = {
        "messaging_product": "whatsapp", "to": to, "type": "template",
        "template": {"name": template, "language": {"code": settings.whatsapp_language},
                     "components": [{"type": "body", "parameters": [{"type": "text", "text": p[:200]} for p in params]}]},
    }
    request = urllib.request.Request(
        f"https://graph.facebook.com/v21.0/{settings.whatsapp_phone_number_id}/messages",
        data=json.dumps(body).encode(), method="POST",
        headers={"Authorization": f"Bearer {settings.whatsapp_token}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:  # noqa: S310 - fixed https host
            return 200 <= response.status < 300
    except Exception:
        logger.warning("WhatsApp message failed (%s)", template, exc_info=True)
        return False


def _push(db, order: Order, title: str, body: str, url: str) -> None:
    from app.services import push

    if not push.enabled():
        return
    from pywebpush import WebPushException, webpush

    gone = []
    payload = json.dumps({"title": title, "body": body, "url": url, "tag": f"pedido-{order.order_number}"})
    for sub in db.scalars(select(OrderPushSubscription).where(OrderPushSubscription.order_id == order.id)):
        try:
            webpush(subscription_info={"endpoint": sub.endpoint, "keys": {"p256dh": sub.p256dh, "auth": sub.auth}}, data=payload,
                    vapid_private_key=settings.vapid_private_key, vapid_claims={"sub": settings.vapid_subject}, ttl=1800, timeout=8)
        except WebPushException as error:
            if getattr(error.response, "status_code", None) in (404, 410):
                gone.append(sub.id)
        except Exception:
            logger.warning("Customer push failed", exc_info=True)
    if gone:
        db.execute(delete(OrderPushSubscription).where(OrderPushSubscription.id.in_(gone)))
        db.commit()


def order_changed(order_id: UUID, status: OrderStatus) -> None:
    with SessionLocal() as db:
        order = db.get(Order, order_id)
        if order is None:
            return
        tenant = db.get(Tenant, order.tenant_id)
        if tenant is None or not tenant.notify_customers:
            return
        text = message(order, tenant, status)
        if text is None:
            return
        title, body = text
        _push(db, order, title, body, settings.tenant_url(tenant.slug, "/"))
        if order.notify_whatsapp and whatsapp_enabled() and order.tab_id is None:
            customer = db.get(Customer, order.customer_id)
            to = _whatsapp_number(customer.phone if customer else None)
            if to:
                first = (customer.name or "").split(" ")[0] or "cliente"
                if status is OrderStatus.READY:
                    send_whatsapp(to, settings.whatsapp_template_ready, [first, str(order.order_number), tenant.name.strip(), ready_hint(order)])
                else:
                    send_whatsapp(to, settings.whatsapp_template_preparing, [first, str(order.order_number), tenant.name.strip()])
