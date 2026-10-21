import uuid

import pytest

from app.core.rate_limit import signup_rate_limit
from tests.conftest import PASSWORD

pytestmark = pytest.mark.integration


def test_signup_creates_tenant_admin_and_starter_categories(make_tenant, client):
    tenant = make_tenant(business_type="CAFE")

    me = tenant.get("/auth/me").json()
    assert me["role"] == "ADMIN"

    names = [c["name"] for c in tenant.get("/categories").json()]
    assert names == ["Cafés", "Bebidas geladas", "Lanches", "Doces"]

    public = tenant.public_get("/tenant").json()
    assert public["slug"] == tenant.slug
    assert public["accepting_orders"] is True


def test_signup_rejects_taken_reserved_and_malformed_slugs(make_tenant, client):
    taken = make_tenant()
    payload = {
        "business_name": "Outro", "slug": taken.slug, "admin_name": "Fulano",
        "email": "x@y.com", "password": PASSWORD, "accept_terms": True,
    }
    assert client.post("/platform/signup", json=payload).status_code == 422

    for bad in ("admin", "www", "Meu Lugar", "ab", "-abc", "a--b"):
        signup_rate_limit.reset()
        response = client.post("/platform/signup", json={**payload, "slug": bad})
        assert response.status_code == 422, bad


def test_slug_availability(make_tenant, client):
    taken = make_tenant()
    assert client.get("/platform/slug-available", params={"slug": taken.slug}).json()["available"] is False
    assert client.get("/platform/slug-available", params={"slug": "admin"}).json()["available"] is False
    free = f"livre-{uuid.uuid4().hex[:8]}"
    assert client.get("/platform/slug-available", params={"slug": free}).json()["available"] is True


def test_same_email_can_exist_in_two_tenants(make_tenant, client, created_slugs):
    first = make_tenant()
    slug = f"outro-{uuid.uuid4().hex[:8]}"
    response = client.post("/platform/signup", json={
        "business_name": "Segundo", "slug": slug, "admin_name": "Mesma Pessoa",
        "email": first.email, "password": PASSWORD, "accept_terms": True,
    })
    created_slugs.append(slug)
    assert response.status_code == 201


def test_signup_requires_accepting_the_terms_and_records_it(client, created_slugs):
    from app.core.database import SessionLocal
    from app.core.legal import TERMS_VERSION
    from app.models.tenant import Tenant
    from sqlalchemy import select

    slug = f"termos-{uuid.uuid4().hex[:8]}"
    payload = {"business_name": "Com Termos", "slug": slug, "admin_name": "Dona", "email": "dona@termos.com", "password": PASSWORD}
    refused = client.post("/platform/signup", json=payload)
    assert refused.status_code == 422 and "Termos de Uso" in str(refused.json())
    signup_rate_limit.reset()
    assert client.post("/platform/signup", json={**payload, "accept_terms": True}).status_code == 201
    created_slugs.append(slug)
    with SessionLocal() as db:
        tenant = db.scalar(select(Tenant).where(Tenant.slug == slug))
        assert tenant.terms_version == TERMS_VERSION and tenant.terms_accepted_at is not None


def test_unknown_tenant_is_404(client):
    assert client.get("/public/menu", headers={"X-Tenant": "nao-existe-aqui"}).status_code == 404
    assert client.get("/public/menu").status_code == 404
