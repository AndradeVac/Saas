"""Subscriptions paid online (Asaas), with the Asaas API faked: nothing here talks to the real service."""
import uuid
from datetime import date, timedelta

import pytest
from sqlalchemy import select, update

from app.core import asaas
from app.core.config import settings
from app.core.database import SessionLocal
from app.models.tenant import Tenant, TenantStatus

CNPJ = "63.148.827/0001-67"
TOKEN = "segredo-do-webhook"


@pytest.fixture
def fake_asaas(monkeypatch):
    calls: dict[str, list] = {"customers": [], "subscriptions": [], "updates": [], "deletes": []}
    monkeypatch.setattr(settings, "asaas_api_key", "fake-key")
    monkeypatch.setattr(settings, "asaas_webhook_token", TOKEN)
    monkeypatch.setattr(asaas, "create_customer", lambda *a: calls["customers"].append(a) or f"cus_{len(calls['customers'])}")
    monkeypatch.setattr(asaas, "create_subscription", lambda *a: calls["subscriptions"].append(a) or {"id": f"sub_{a[3][:8]}"})
    monkeypatch.setattr(asaas, "update_subscription", lambda *a: calls["updates"].append(a) or {})
    monkeypatch.setattr(asaas, "delete_subscription", lambda sid: calls["deletes"].append(sid))
    monkeypatch.setattr(asaas, "pending_payment_url", lambda sid: f"https://www.asaas.com/i/{sid}")
    return calls


def tenant_row(slug):
    with SessionLocal() as db:
        return db.scalar(select(Tenant).where(Tenant.slug == slug))


RUN = uuid.uuid4().hex[:8]  # event ids are global (idempotency table): unique per test run


def webhook(client, event, subscription_id, event_id, due=None, token=TOKEN):
    payload = {"id": f"{event_id}_{RUN}_{subscription_id}", "event": event, "payment": {"id": "pay_1", "subscription": subscription_id, "dueDate": (due or date.today()).isoformat()}}
    return client.post("/billing/webhook", json=payload, headers={"asaas-access-token": token} if token else {})


def test_subscribe_and_first_payment_activates_the_plan(make_tenant, client, fake_asaas):
    shop = make_tenant(plan=None)
    assert shop.post("/billing/subscribe", {"plan": "essencial", "document": "111.111.111-11", "email": "dono@x.com"}).status_code == 422
    response = shop.post("/billing/subscribe", {"plan": "essencial", "document": CNPJ, "email": "dono@x.com"})
    assert response.status_code == 200 and response.json()["checkout_url"].startswith("https://www.asaas.com/i/")
    assert fake_asaas["subscriptions"][0][1] == "79.90"  # value of the plan
    status = shop.get("/tenant/plan").json()
    assert status["billing_status"] == "PENDING" and status["plan"]["key"] == "trial"  # nothing unlocked before paying

    sub = tenant_row(shop.slug).billing_subscription_id
    assert webhook(client, "PAYMENT_CONFIRMED", sub, "evt_1", token=None).status_code == 401
    assert webhook(client, "PAYMENT_CONFIRMED", sub, "evt_1", token="errado").status_code == 401
    assert webhook(client, "PAYMENT_CONFIRMED", sub, "evt_1").json()["result"] == "ok"
    status = shop.get("/tenant/plan").json()
    assert status["billing_status"] == "ACTIVE" and status["plan"]["key"] == "essencial" and status["status"] == "ACTIVE"
    assert date.fromisoformat(status["paid_until"]) > date.today()
    assert shop.get("/coupons").status_code == 200  # Essencial unlocks coupons
    assert webhook(client, "PAYMENT_CONFIRMED", sub, "evt_1").json()["result"] == "duplicate"


def test_overdue_grace_period_then_block_and_recover(make_tenant, client, fake_asaas):
    shop = make_tenant(plan=None)
    product = shop.add_product(price="30.00")
    shop.post("/billing/subscribe", {"plan": "pro", "document": CNPJ, "email": "dono@x.com"})
    sub = tenant_row(shop.slug).billing_subscription_id
    webhook(client, "PAYMENT_CONFIRMED", sub, "evt_a")

    webhook(client, "PAYMENT_OVERDUE", sub, "evt_b")
    status = shop.get("/tenant/plan").json()
    assert status["billing_status"] == "OVERDUE" and status["billing_blocked"] is False and status["grace_until"]
    assert shop.public_order(product["id"], service_type="TAKEAWAY", payment_method="PIX").status_code == 201  # still in grace

    with SessionLocal() as db:
        db.execute(update(Tenant).where(Tenant.slug == shop.slug).values(past_due_since=date.today() - timedelta(days=settings.billing_grace_days + 1)))
        db.commit()
    assert shop.get("/tenant/plan").json()["billing_blocked"] is True
    assert shop.public_order(product["id"], service_type="TAKEAWAY", payment_method="PIX").status_code == 422

    webhook(client, "PAYMENT_RECEIVED", sub, "evt_c")
    assert shop.get("/tenant/plan").json()["billing_blocked"] is False
    assert shop.public_order(product["id"], service_type="TAKEAWAY", payment_method="PIX").status_code == 201


def test_change_plan_and_cancel(make_tenant, client, fake_asaas):
    shop = make_tenant(plan=None)
    shop.post("/billing/subscribe", {"plan": "essencial", "document": CNPJ, "email": "dono@x.com"})
    sub = tenant_row(shop.slug).billing_subscription_id
    webhook(client, "PAYMENT_CONFIRMED", sub, "evt_x")

    shop.post("/billing/subscribe", {"plan": "pro", "document": CNPJ, "email": "dono@x.com"})
    assert fake_asaas["updates"][0][1] == "149.90" and len(fake_asaas["subscriptions"]) == 1
    assert shop.get("/tenant/plan").json()["plan"]["key"] == "pro"

    assert shop.post("/billing/cancel").status_code == 204 and fake_asaas["deletes"] == [sub]
    status = shop.get("/tenant/plan").json()
    assert status["billing_status"] == "CANCELED" and status["billing_blocked"] is False  # paid period still running
    with SessionLocal() as db:
        db.execute(update(Tenant).where(Tenant.slug == shop.slug).values(paid_until=date.today() - timedelta(days=1)))
        db.commit()
    assert shop.get("/tenant/plan").json()["billing_blocked"] is True


def test_catalog_says_when_billing_is_online(client, fake_asaas, monkeypatch):
    assert client.get("/platform/plans").json()["online_billing"] is True
    monkeypatch.setattr(settings, "asaas_api_key", "")
    assert client.get("/platform/plans").json()["online_billing"] is False


def test_operator_cannot_subscribe(make_tenant, client, fake_asaas):
    shop = make_tenant()  # paid plan: the trial allows only the owner
    shop.post("/users", {"name": "Op", "email": f"op@{shop.slug}.com", "password": "senha-segura-123", "role": "OPERATOR"})
    operator = type(shop)(client, shop.slug, f"op@{shop.slug}.com")
    operator.login(password="senha-segura-123")
    assert operator.post("/billing/subscribe", {"plan": "pro", "document": CNPJ, "email": "x@x.com"}).status_code == 403


def test_courtesy_gives_the_full_plan_until_a_date(make_tenant, client, fake_asaas):
    shop = make_tenant(plan=None)
    product = shop.add_product(price="30.00")
    end = date.today() + timedelta(days=15)
    with SessionLocal() as db:
        db.execute(update(Tenant).where(Tenant.slug == shop.slug).values(status=TenantStatus.ACTIVE, plan="pro", billing_status="COURTESY", paid_until=end))
        db.commit()
    status = shop.get("/tenant/plan").json()
    assert status["plan"]["key"] == "pro" and status["billing_blocked"] is False
    assert shop.get("/coupons").status_code == 200

    # Subscribing during the courtesy: the first charge is due when the courtesy ends.
    shop.post("/billing/subscribe", {"plan": "essencial", "document": CNPJ, "email": "dono@x.com"})
    assert fake_asaas["subscriptions"][0][4] == end.isoformat()
    assert shop.get("/tenant/plan").json()["billing_blocked"] is False

    # Courtesy over and the first charge not paid: orders stop.
    with SessionLocal() as db:
        db.execute(update(Tenant).where(Tenant.slug == shop.slug).values(paid_until=date.today() - timedelta(days=1)))
        db.commit()
    assert shop.get("/tenant/plan").json()["billing_blocked"] is True
    assert shop.public_order(product["id"], service_type="TAKEAWAY", payment_method="PIX").status_code == 422
    webhook(client, "PAYMENT_CONFIRMED", tenant_row(shop.slug).billing_subscription_id, "evt_courtesy")
    status = shop.get("/tenant/plan").json()
    assert status["billing_status"] == "ACTIVE" and status["plan"]["key"] == "essencial" and status["billing_blocked"] is False


def test_annual_plan_charges_ten_months_and_lasts_a_year(make_tenant, client, fake_asaas):
    shop = make_tenant(plan=None)
    response = shop.post("/billing/subscribe", {"plan": "essencial", "document": CNPJ, "email": "dono@x.com", "cycle": "YEARLY"})
    assert response.status_code == 200
    assert fake_asaas["subscriptions"][0][1] == "799.00" and fake_asaas["subscriptions"][0][5] == "YEARLY"
    sub = tenant_row(shop.slug).billing_subscription_id
    webhook(client, "PAYMENT_CONFIRMED", sub, "evt_year")
    status = shop.get("/tenant/plan").json()
    assert status["billing_cycle"] == "YEARLY" and date.fromisoformat(status["paid_until"]) > date.today() + timedelta(days=330)
    assert shop.post("/billing/subscribe", {"plan": "pro", "document": CNPJ, "email": "d@x.com", "cycle": "WEEKLY"}).status_code == 422
