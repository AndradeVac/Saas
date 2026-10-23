"""Lifecycle e-mails (once each), referrals and the platform panel."""
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.lifecycle_email import LifecycleEmail
from app.models.tenant import Tenant, TenantStatus
from app.services import lifecycle


def _tenant(slug):
    with SessionLocal() as db:
        return db.scalar(select(Tenant).where(Tenant.slug == slug))


def test_trial_emails_go_out_once(make_tenant, monkeypatch):
    sent = []
    monkeypatch.setattr(lifecycle, "send_email", lambda to, subject, html, text: sent.append((to, subject)) or True)
    shop = make_tenant(plan=None)
    noon = datetime.now(timezone.utc).replace(hour=15, minute=0)  # 12:00 in São Paulo
    with SessionLocal() as db:
        db.execute(update(Tenant).where(Tenant.slug == shop.slug).values(trial_ends_at=noon + timedelta(days=3, hours=2)))
        db.commit()
    lifecycle.run(noon)
    lifecycle.run(noon)  # second pass: nothing new
    mine = [s for s in sent if s[0] == shop.email]
    assert len([s for s in mine if "faltam 3 dias" in s[1]]) == 1
    with SessionLocal() as db:
        kinds = set(db.scalars(select(LifecycleEmail.kind).where(LifecycleEmail.tenant_id == _tenant(shop.slug).id)))
    assert "trial_3d" in kinds


def test_welcome_email_on_signup(make_tenant, monkeypatch):
    sent = []
    monkeypatch.setattr(lifecycle, "send_email", lambda to, subject, html, text: sent.append((to, subject, html)) or True)
    shop = make_tenant(plan=None)
    assert any(to == shop.email and "Bem-vindo" in subject for to, subject, _ in sent)


def test_signup_records_the_referrer(make_tenant, client, created_slugs):
    referrer = make_tenant()
    slug = f"indicado-{referrer.slug[-6:]}"
    response = client.post("/platform/signup", json={"business_name": "Indicado", "slug": slug, "admin_name": "Dono", "phone": "11987654321",
                                                    "email": f"dono@{slug}.com", "password": "senha-segura-123", "accept_terms": True, "referred_by": referrer.slug})
    created_slugs.append(slug)
    assert response.status_code == 201 and _tenant(slug).referred_by == referrer.slug


def test_platform_panel_needs_the_token(make_tenant, client, monkeypatch):
    make_tenant()
    monkeypatch.setattr(settings, "platform_admin_token", "")
    assert client.get("/platform/admin/overview", headers={"X-Admin-Token": "x"}).status_code == 404
    monkeypatch.setattr(settings, "platform_admin_token", "segredo-forte")
    assert client.get("/platform/admin/overview", headers={"X-Admin-Token": "errado"}).status_code == 404
    data = client.get("/platform/admin/overview", headers={"X-Admin-Token": "segredo-forte"}).json()
    assert data["stores"] >= 1 and "mrr" in data and data["list"][0]["slug"]
