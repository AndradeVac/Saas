"""The point of a multi-tenant system: one tenant must never see or touch another's data."""
import pytest

pytestmark = pytest.mark.integration


def test_login_only_works_on_own_tenant(make_tenant, client):
    first, second = make_tenant(), make_tenant()
    wrong_tenant = client.post(
        "/auth/login",
        data={"username": first.email, "password": "senha-segura-123"},
        headers=second.tenant_headers,
    )
    assert wrong_tenant.status_code == 401


def test_token_is_rejected_on_another_tenant(make_tenant, client):
    first, second = make_tenant(), make_tenant()
    response = client.get("/auth/me", headers={"X-Tenant": second.slug, "Authorization": f"Bearer {first.token}"})
    assert response.status_code == 401


def test_catalog_is_isolated(make_tenant):
    first, second = make_tenant(), make_tenant()
    product = first.add_product("Segredo da casa")

    assert [p["name"] for p in second.get("/products").json()] == []
    assert second.get(f"/products/{product['id']}").status_code == 404
    assert second.patch(f"/products/{product['id']}", {"price": "1.00"}).status_code == 404
    assert second.delete(f"/products/{product['id']}").status_code == 404

    menu_names = [p["name"] for p in second.public_get("/public/menu").json()["products"]]
    assert "Segredo da casa" not in menu_names
    # The owner's product is untouched.
    assert first.get(f"/products/{product['id']}").json()["price"] == "4.50"


def test_cannot_use_another_tenants_category_or_product(make_tenant):
    first, second = make_tenant(), make_tenant()
    foreign_category = first.category_id()
    response = second.post("/products", {"category_id": foreign_category, "name": "Intruso", "price": "1.00"})
    assert response.status_code == 404

    foreign_product = first.add_product()
    order = second.public_order(foreign_product["id"])
    assert order.status_code == 404


def test_orders_and_numbering_are_per_tenant(make_tenant):
    first, second = make_tenant(), make_tenant()
    first_product, second_product = first.add_product(), second.add_product()

    a1 = first.public_order(first_product["id"]).json()
    a2 = first.public_order(first_product["id"], phone="11977776666").json()
    b1 = second.public_order(second_product["id"]).json()
    assert (a1["order_number"], a2["order_number"], b1["order_number"]) == (1, 2, 1)

    assert len(first.get("/orders").json()["items"]) == 2
    assert len(second.get("/orders").json()["items"]) == 1

    # Tracking tokens only resolve inside their own tenant.
    assert first.public_get(f"/public/orders/{a1['public_token']}").status_code == 200
    assert second.public_get(f"/public/orders/{a1['public_token']}").status_code == 404

    order_id = first.get("/orders").json()["items"][0]["id"]
    assert second.get(f"/orders/{order_id}").status_code == 404
    assert second.patch(f"/orders/{order_id}/status", {"status": "PREPARING"}).status_code == 404


def test_customers_users_and_audit_are_isolated(make_tenant):
    first, second = make_tenant(), make_tenant()
    product = first.add_product()
    first.public_order(product["id"])

    assert second.get("/customers").json()["items"] == []
    assert len(second.get("/users").json()) == 1
    audit_actions = {entry["action"] for entry in second.get("/audit").json()["items"]}
    assert "PRODUCT_CREATED" not in audit_actions
    assert "ORDER_STATUS_CHANGED" not in audit_actions


def test_tabs_and_public_links_are_isolated(make_tenant):
    """A comanda or order link from one store is useless on another store's address."""
    first, second = make_tenant(), make_tenant()
    assert first.patch("/tenant/settings", {"tabs_enabled": True, "min_order_value": "0"}).status_code == 200
    beer = first.add_product("Chope", "12.00")
    order = first.public_order(beer["id"], quantity=1, table_label="7", table_code=first.table_code("7"))
    assert order.status_code == 201, order.text
    tab_token, order_token = order.json()["tab_token"], order.json()["public_token"]
    tab_id = first.get("/tabs").json()[0]["id"]

    assert second.get("/tabs").json() == []
    assert second.get(f"/tabs/{tab_id}").status_code == 404
    assert second.post(f"/tabs/{tab_id}/approve").status_code == 404
    assert second.public_get(f"/public/tabs/{tab_token}").status_code == 404
    assert second.public_get(f"/public/orders/{order_token}").status_code == 404
    assert second.public_get(f"/public/tables/7/tab", params={"k": first.table_code("7")}).status_code in (404, 422)
    assert first.public_get(f"/public/tabs/{tab_token}").status_code == 200  # still fine at home


def test_coupons_reports_and_export_are_isolated(make_tenant):
    first, second = make_tenant(), make_tenant()
    coupon = first.post("/coupons", {"code": "SEGREDO10", "kind": "PERCENT", "value": "10"})
    assert coupon.status_code == 201, coupon.text
    product = first.add_product("Pastel", "50.00")
    assert first.public_order(product["id"], quantity=2).status_code == 201

    assert second.get("/coupons").json() == []
    assert second.patch(f"/coupons/{coupon.json()['id']}", {"active": False}).status_code == 404
    assert second.public_post("/public/coupons/check", {"code": "SEGREDO10", "subtotal": "50.00"}).status_code != 200
    assert second.get("/analytics/dashboard", params={"period": "all"}).json()["order_count"] == 0
    assert second.get("/analytics/cash").json()["orders"] == 0
    exported = second.get("/tenant/export").json()
    assert exported["customers"] == [] and exported["orders"] == []
