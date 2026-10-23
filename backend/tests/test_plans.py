"""Plans: the trial shows everything for 14 days; paid plans cap volume and lock tools (402)."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from app.core.plans import PLANS
from app.models.tenant import TenantStatus
from tests.conftest import set_plan

TRIAL = PLANS["trial"]


def test_trial_unlocks_everything_but_white_label(make_tenant):
    shop = make_tenant(plan=None)
    for path in ("/coupons", "/audit", "/customers/export", "/orders/export", "/analytics/dashboard/export", "/analytics/insights"):
        assert shop.get(path).status_code == 200, path
    status = shop.get("/tenant/plan").json()
    assert status["plan"]["key"] == "trial" and status["trial_days_left"] >= 13
    assert status["plan"]["max_products"] is None and status["plan"]["max_orders"] is None
    assert shop.public_get("/tenant").json()["show_platform_badge"] is True  # the badge stays while testing


def test_paid_plan_caps_products_and_team(make_tenant):
    shop = make_tenant(plan="essencial")
    essencial = PLANS["essencial"]
    PLANS["essencial"] = replace(essencial, max_products=3, max_users=1)
    try:
        products = [shop.add_product(name=f"Produto {i}") for i in range(3)]
        response = shop.post("/products", {"category_id": shop.category_id(), "name": "Um a mais", "price": "1.00"})
        assert response.status_code == 402 and response.json()["feature"] == "max_products"
        # Freeing a slot allows a new one; reactivating the old one is capped again.
        assert shop.delete(f"/products/{products[0]['id']}").status_code == 200
        shop.add_product(name="Substituto")
        assert shop.patch(f"/products/{products[0]['id']}", {"active": True}).status_code == 402
        response = shop.post("/users", {"name": "Operador", "email": f"op@{shop.slug}.com", "password": "senha-segura-123", "role": "OPERATOR"})
        assert response.status_code == 402
    finally:
        PLANS["essencial"] = essencial


def test_coupons_work_while_on_trial(make_tenant):
    shop = make_tenant(plan=None)
    assert shop.post("/coupons", {"code": "BEMVINDO", "kind": "PERCENT", "value": "10"}).status_code == 201
    product = shop.add_product(price="10.00")
    assert shop.public_order(product["id"], quantity=1, coupon_code="BEMVINDO").status_code == 201


def test_trial_order_cap_closes_the_menu(make_tenant):
    shop = make_tenant(plan=None)
    product = shop.add_product()
    PLANS["trial"] = replace(TRIAL, max_orders=1)
    try:
        assert shop.public_order(product["id"]).status_code == 201
        assert shop.public_get("/tenant").json()["is_open"] is False
        response = shop.public_order(product["id"])
        assert response.status_code == 422
        assert "não está aceitando pedidos" in response.json()["detail"]
        assert shop.get("/tenant/plan").json()["can_take_orders"] is False
    finally:
        PLANS["trial"] = TRIAL


def test_expired_trial_stops_orders_but_keeps_the_panel(make_tenant):
    shop = make_tenant(plan=None)
    product = shop.add_product()
    set_plan(shop.slug, "trial", TenantStatus.TRIAL, trial_ends_at=datetime.now(timezone.utc) - timedelta(minutes=1))

    assert shop.public_order(product["id"]).status_code == 422
    status = shop.get("/tenant/plan").json()
    assert status["trial_expired"] is True and status["trial_days_left"] == 0
    # The owner can keep polishing the menu while deciding.
    assert shop.patch(f"/products/{product['id']}", {"price": "5.00"}).status_code == 200


def test_paid_plans_unlock_and_catalog_is_public(client, make_tenant):
    shop = make_tenant(plan="pro")
    assert shop.get("/coupons").status_code == 200
    assert shop.public_get("/tenant").json()["show_platform_badge"] is False

    catalog = client.get("/platform/plans").json()
    assert [p["key"] for p in catalog["plans"]] == list(PLANS)
    assert catalog["feature_names"]["coupons"]
