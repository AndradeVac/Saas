"""Automatic customer messages when the order moves (WhatsApp official API faked, push subscriptions)."""
from app.core.config import settings
from app.services import customer_notify


def _order(shop, notify=True, service="TAKEAWAY"):
    product = shop.add_product(price="20.00")
    created = shop.public_order(product["id"], quantity=1, service_type=service, payment_method="CASH",
                                customer_name="Joana Silva", phone="11988887777", notify_whatsapp=notify).json()
    order = next(o for o in shop.get("/orders").json()["items"] if o["order_number"] == created["order_number"])
    return created, order


def test_whatsapp_when_preparing_and_ready(make_tenant, monkeypatch):
    sent = []
    monkeypatch.setattr(settings, "whatsapp_token", "token")
    monkeypatch.setattr(settings, "whatsapp_phone_number_id", "123")
    monkeypatch.setattr(customer_notify, "send_whatsapp", lambda to, template, params: sent.append((to, template, params)) or True)
    shop = make_tenant()
    shop.patch("/tenant/settings", {"enabled_services": ["TAKEAWAY", "DELIVERY"]})
    assert shop.public_get("/tenant").json()["whatsapp_notifications"] is True
    created, order = _order(shop)
    shop.patch(f"/orders/{order['id']}/status", {"status": "PREPARING"})
    shop.patch(f"/orders/{order['id']}/status", {"status": "READY"})
    assert [s[1] for s in sent] == ["pedido_em_preparo", "pedido_pronto"]
    to, _, params = sent[1]
    assert to == "5511988887777" and params[0] == "Joana" and params[1] == str(created["order_number"]) and params[3] == "Pode retirar no balcão."

    # No checkbox, no message; store switched off, no message.
    sent.clear()
    _, quiet = _order(shop, notify=False)
    shop.patch(f"/orders/{quiet['id']}/status", {"status": "PREPARING"})
    shop.patch("/tenant/settings", {"notify_customers": False})
    _, off = _order(shop)
    shop.patch(f"/orders/{off['id']}/status", {"status": "PREPARING"})
    assert sent == []


def test_ready_message_depends_on_the_service(make_tenant):
    from types import SimpleNamespace

    from app.models.order import ServiceType
    assert customer_notify.ready_hint(SimpleNamespace(service_type=ServiceType.DELIVERY, table_label=None)).startswith("Ele já está saindo")
    assert "mesa 4" in customer_notify.ready_hint(SimpleNamespace(service_type=ServiceType.DINE_IN, table_label="4"))


def test_customer_can_subscribe_the_phone_to_order_updates(make_tenant):
    shop = make_tenant()
    shop.patch("/tenant/settings", {"enabled_services": ["TAKEAWAY"]})
    created, _ = _order(shop)
    body = {"endpoint": "https://push.example.com/cliente", "keys": {"p256dh": "k" * 20, "auth": "a" * 10}}
    assert shop.public_post(f"/public/orders/{created['public_token']}/push", body).status_code == 204
    assert shop.public_post(f"/public/orders/{created['public_token']}/push", body).status_code == 204  # idempotent
    assert shop.public_post(f"/public/orders/{created['public_token']}/push", {**body, "endpoint": "http://x.com/abc"}).status_code == 422
