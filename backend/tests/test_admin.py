import pytest

from tests.conftest import PASSWORD

pytestmark = pytest.mark.integration


def test_operator_cannot_manage_catalog_or_team(make_tenant):
    tenant = make_tenant()
    created = tenant.post("/users", {"name": "Caixa", "email": f"caixa@{tenant.slug}.com", "password": PASSWORD, "role": "OPERATOR"})
    assert created.status_code == 201

    operator = type(tenant)(tenant.client, tenant.slug, f"caixa@{tenant.slug}.com")
    assert operator.login().status_code == 200

    category = operator.category_id()
    assert operator.post("/products", {"category_id": category, "name": "X", "price": "1"}).status_code == 403
    assert operator.get("/users").status_code == 403
    assert operator.get("/audit").status_code == 403
    assert operator.get("/analytics/dashboard").status_code == 403
    assert operator.patch("/tenant/settings", {"name": "Hackeado"}).status_code == 403
    # ...but can run the floor.
    assert operator.get("/orders").status_code == 200
    assert operator.get("/products").status_code == 200


def test_last_admin_cannot_be_deactivated(make_tenant):
    tenant = make_tenant()
    me = tenant.get("/auth/me").json()
    assert tenant.patch(f"/users/{me['id']}/status", {"active": False}).status_code == 422


def test_inactive_user_loses_access(make_tenant):
    tenant = make_tenant()
    staff = tenant.post("/users", {"name": "Garçom", "email": f"g@{tenant.slug}.com", "password": PASSWORD}).json()
    session = type(tenant)(tenant.client, tenant.slug, f"g@{tenant.slug}.com")
    assert session.login().status_code == 200

    tenant.patch(f"/users/{staff['id']}/status", {"active": False})
    assert session.get("/auth/me").status_code == 401
    assert session.login().status_code == 401


def test_change_password(make_tenant, client):
    tenant = make_tenant()
    assert tenant.post("/auth/password", {"current_password": "errada", "new_password": "nova-senha-123"}).status_code == 422
    assert tenant.post("/auth/password", {"current_password": PASSWORD, "new_password": "nova-senha-123"}).status_code == 204
    assert tenant.login(password=PASSWORD).status_code == 401
    assert tenant.login(password="nova-senha-123").status_code == 200


def test_settings_update_validates_color(make_tenant):
    tenant = make_tenant()
    assert tenant.patch("/tenant/settings", {"primary_color": "vermelho"}).status_code == 422
    updated = tenant.patch("/tenant/settings", {"primary_color": "#1D4ED8", "name": "Novo Nome"}).json()
    assert updated["primary_color"] == "#1d4ed8" and updated["name"] == "Novo Nome"


def test_category_duplicate_and_restore(make_tenant):
    tenant = make_tenant()
    created = tenant.post("/categories", {"name": "Promoções"}).json()
    assert tenant.post("/categories", {"name": "Promoções"}).status_code == 409

    tenant.delete(f"/categories/{created['id']}")
    restored = tenant.post("/categories", {"name": "Promoções"})
    assert restored.status_code == 201 and restored.json()["active"] is True


def test_dashboard_counts_sales_and_excludes_cancelled(make_tenant):
    tenant = make_tenant()
    product = tenant.add_product("Café", "5.00")
    tenant.public_order(product["id"], quantity=2)
    tenant.public_order(product["id"], quantity=1, phone="11977770000")
    cancelled_id = tenant.get("/orders").json()["items"][0]["id"]
    tenant.patch(f"/orders/{cancelled_id}/status", {"status": "CANCELLED", "reason": "teste"})

    dashboard = tenant.get("/analytics/dashboard", params={"period": "all"}).json()
    assert dashboard["order_count"] == 1
    assert dashboard["products"][0]["product_name"] == "Café"
    assert len(dashboard["sales_by_hour"]) == 1 and len(dashboard["sales_by_day"]) == 1
    assert tenant.get("/analytics/dashboard", params={"period": "month"}).status_code == 200
    assert tenant.get("/analytics/dashboard/export", params={"format": "xlsx"}).status_code == 200
    assert tenant.get("/analytics/dashboard/export", params={"format": "pdf"}).status_code == 200
    assert tenant.get("/analytics/dashboard", params={"start": "2026-02-10", "end": "2026-02-01"}).status_code == 422
