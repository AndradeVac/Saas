"""Integration tests run against the DATABASE_URL database. Every test tenant uses a random slug
and is deleted afterwards (ON DELETE CASCADE removes all of its data)."""
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.core.database import SessionLocal
from app.core.rate_limit import (
    login_rate_limit,
    public_lookup_rate_limit,
    public_order_rate_limit,
    signup_rate_limit,
    slug_check_rate_limit,
)
from app.main import app
from app.models.tenant import Tenant

PASSWORD = "senha-segura-123"


@pytest.fixture(autouse=True)
def reset_rate_limits():
    for limiter in (login_rate_limit, signup_rate_limit, slug_check_rate_limit, public_order_rate_limit, public_lookup_rate_limit):
        limiter.reset()
    yield


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def created_slugs():
    slugs: list[str] = []
    yield slugs
    with SessionLocal() as db:
        db.execute(delete(Tenant).where(Tenant.slug.in_(slugs)))
        db.commit()


class TenantSession:
    """A tenant created through the public sign-up plus helpers to call the API as that tenant."""

    def __init__(self, client: TestClient, slug: str, email: str):
        self.client = client
        self.slug = slug
        self.email = email
        self.token: str | None = None

    @property
    def tenant_headers(self) -> dict[str, str]:
        return {"X-Tenant": self.slug}

    @property
    def auth_headers(self) -> dict[str, str]:
        assert self.token, "call login() first"
        return {"X-Tenant": self.slug, "Authorization": f"Bearer {self.token}"}

    def login(self, email: str | None = None, password: str = PASSWORD):
        response = self.client.post(
            "/auth/login",
            data={"username": email or self.email, "password": password},
            headers=self.tenant_headers,
        )
        if response.status_code == 200:
            self.token = response.json()["access_token"]
        return response

    def get(self, path: str, **kwargs):
        return self.client.get(path, headers=self.auth_headers, **kwargs)

    def post(self, path: str, json=None):
        return self.client.post(path, json=json, headers=self.auth_headers)

    def patch(self, path: str, json=None):
        return self.client.patch(path, json=json, headers=self.auth_headers)

    def delete(self, path: str):
        return self.client.delete(path, headers=self.auth_headers)

    def public_get(self, path: str, **kwargs):
        return self.client.get(path, headers=self.tenant_headers, **kwargs)

    def public_post(self, path: str, json=None):
        return self.client.post(path, json=json, headers=self.tenant_headers)

    # -- shortcuts --------------------------------------------------------------------------
    def category_id(self, name: str | None = None) -> str:
        categories = self.get("/categories").json()
        return next(c["id"] for c in categories if name is None or c["name"] == name)

    def add_product(self, name: str = "Pão de queijo", price: str = "4.50", **extra) -> dict:
        response = self.post("/products", {"category_id": self.category_id(), "name": name, "price": price, **extra})
        assert response.status_code == 201, response.text
        return response.json()

    def public_order(self, product_id: str, quantity: int = 2, phone: str = "11999998888", **extra):
        return self.public_post("/public/orders", {
            "customer_name": "Maria Cliente",
            "customer_phone": phone,
            "items": [{"product_id": product_id, "quantity": quantity}],
            **extra,
        })


@pytest.fixture
def make_tenant(client, created_slugs):
    def factory(prefix: str = "t", business_type: str = "BAKERY") -> TenantSession:
        slug = f"{prefix}-{uuid.uuid4().hex[:10]}"
        email = f"admin@{slug}.com"
        response = client.post("/platform/signup", json={
            "business_name": f"Negócio {slug}",
            "business_type": business_type,
            "slug": slug,
            "admin_name": "Dono do Negócio",
            "email": email,
            "password": PASSWORD,
        })
        assert response.status_code == 201, response.text
        created_slugs.append(slug)
        session = TenantSession(client, slug, email)
        assert session.login().status_code == 200
        return session

    return factory
