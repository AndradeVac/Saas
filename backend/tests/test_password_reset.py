""""Esqueci minha senha": single-use, one-hour link by e-mail; never reveals which e-mails exist."""
import re
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import update

from app.core.database import SessionLocal
from app.models.password_reset import PasswordResetToken
from app.services import password_reset
from tests.conftest import PASSWORD


@pytest.fixture
def outbox(monkeypatch):
    sent: list[dict] = []
    monkeypatch.setattr(password_reset, "send_email", lambda to, subject, html, text: sent.append({"to": to, "text": text}) or True)
    return sent


def token_from(mail: dict) -> str:
    return re.search(r"token=([\w-]+)", mail["text"]).group(1)


def test_reset_flow(make_tenant, client, outbox):
    shop = make_tenant()
    assert client.post("/auth/forgot-password", json={"email": shop.email.upper()}, headers=shop.tenant_headers).status_code == 204
    assert len(outbox) == 1 and outbox[0]["to"] == shop.email
    assert f"{shop.slug}." in outbox[0]["text"] and "/redefinir-senha?token=" in outbox[0]["text"]
    token = token_from(outbox[0])

    response = client.post("/auth/reset-password", json={"token": token, "new_password": "nova-senha-forte"}, headers=shop.tenant_headers)
    assert response.status_code == 204
    assert shop.login(password=PASSWORD).status_code == 401
    assert shop.login(password="nova-senha-forte").status_code == 200

    # Single use.
    again = client.post("/auth/reset-password", json={"token": token, "new_password": "outra-senha-123"}, headers=shop.tenant_headers)
    assert again.status_code == 422


def test_unknown_email_answers_the_same_and_sends_nothing(make_tenant, client, outbox):
    shop = make_tenant()
    assert client.post("/auth/forgot-password", json={"email": "ninguem@exemplo.com"}, headers=shop.tenant_headers).status_code == 204
    assert outbox == []


def test_new_request_invalidates_old_link_and_links_expire(make_tenant, client, outbox):
    shop = make_tenant()
    client.post("/auth/forgot-password", json={"email": shop.email}, headers=shop.tenant_headers)
    client.post("/auth/forgot-password", json={"email": shop.email}, headers=shop.tenant_headers)
    old, new = token_from(outbox[0]), token_from(outbox[1])
    assert client.post("/auth/reset-password", json={"token": old, "new_password": "nova-senha-forte"}, headers=shop.tenant_headers).status_code == 422

    with SessionLocal() as db:
        db.execute(update(PasswordResetToken).values(expires_at=datetime.now(timezone.utc) - timedelta(minutes=1)))
        db.commit()
    assert client.post("/auth/reset-password", json={"token": new, "new_password": "nova-senha-forte"}, headers=shop.tenant_headers).status_code == 422


def test_link_only_works_on_its_own_business(make_tenant, client, outbox):
    shop, other = make_tenant("a"), make_tenant("b")
    client.post("/auth/forgot-password", json={"email": shop.email}, headers=shop.tenant_headers)
    token = token_from(outbox[0])
    assert client.post("/auth/reset-password", json={"token": token, "new_password": "nova-senha-forte"}, headers=other.tenant_headers).status_code == 422
    assert shop.login().status_code == 200
