"""Panel operations: end-of-day cash report and new-order push subscriptions."""
from decimal import Decimal

from app.core.config import settings
from app.services import push


def test_cash_report_sums_the_day_by_payment_method(make_tenant):
    shop = make_tenant()
    shop.patch("/tenant/settings", {"accepted_payments": ["PIX", "CASH", "CARD"], "enabled_services": ["TAKEAWAY", "DINE_IN"], "min_order_value": "0"})
    product = shop.add_product(price="20.00")
    paid_cash = shop.public_order(product["id"], quantity=1, service_type="TAKEAWAY", payment_method="CASH").json()
    paid_card = shop.public_order(product["id"], quantity=2, service_type="TAKEAWAY", payment_method="CARD").json()
    shop.public_order(product["id"], quantity=1, service_type="TAKEAWAY", payment_method="CASH")  # not paid yet
    cancelled = shop.public_order(product["id"], quantity=1, service_type="TAKEAWAY", payment_method="CASH").json()
    orders = {o["order_number"]: o for o in shop.get("/orders").json()["items"]}
    for created in (paid_cash, paid_card):
        shop.patch(f"/orders/{orders[created['order_number']]['id']}/payment", {"payment_status": "PAID"})
    shop.patch(f"/orders/{orders[cancelled['order_number']]['id']}/status", {"status": "CANCELLED", "reason": "teste"})

    report = shop.get("/analytics/cash").json()
    by_method = {r["method"]: r for r in report["received"]}
    assert Decimal(by_method["CARD"]["amount"]) == Decimal("40.00") and Decimal(by_method["CASH"]["amount"]) == Decimal("20.00")
    assert Decimal(report["received_total"]) == Decimal("60.00")
    assert report["orders"] == 3 and report["cancelled"] == 1 and report["pending_orders"] == 1
    assert shop.get("/analytics/cash", params={"day": "2020-01-01"}).json()["received"] == []


def test_push_subscription(make_tenant, monkeypatch):
    shop = make_tenant()
    body = {"endpoint": "https://push.example.com/abc", "keys": {"p256dh": "x" * 20, "auth": "y" * 10}}
    monkeypatch.setattr(settings, "vapid_public_key", "")
    assert shop.get("/push/public-key").json() == {"key": None}
    assert shop.post("/push/subscribe", body).status_code == 422
    monkeypatch.setattr(settings, "vapid_public_key", "pub")
    monkeypatch.setattr(settings, "vapid_private_key", "priv")
    assert shop.post("/push/subscribe", body).status_code == 204
    assert shop.post("/push/subscribe", body).status_code == 204  # same browser twice: still one row
    sent = []
    monkeypatch.setattr(push, "notify_tenant", lambda *args: sent.append(args))
    product = shop.add_product(price="10.00")
    shop.public_order(product["id"], quantity=1)
    assert sent and sent[0][1].startswith("Novo pedido #")
    assert shop.post("/push/unsubscribe", {"endpoint": body["endpoint"]}).status_code == 204
