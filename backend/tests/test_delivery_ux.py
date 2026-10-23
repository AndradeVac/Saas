"""Delivery zones, PIX up front for deliveries, customer cancellation and link previews."""
from decimal import Decimal

from fastapi.testclient import TestClient


def _store(shop, **extra):
    shop.patch("/tenant/settings", {"enabled_services": ["DINE_IN", "TAKEAWAY", "DELIVERY"], "accepted_payments": ["PIX", "CASH"],
                                    "pix_key": "dono@loja.com", "delivery_fee": "7.00", "min_order_value": "0", **extra})
    return shop.add_product(price="30.00")


def test_delivery_zones_price_the_fee_by_neighbourhood(make_tenant):
    shop = make_tenant()
    product = _store(shop, delivery_zones=[{"name": "Centro", "fee": "4.00"}, {"name": "Jardim", "fee": "9.50"}])
    assert shop.public_get("/tenant").json()["delivery_zones"][1] == {"name": "Jardim", "fee": "9.50"}
    no_zone = shop.public_order(product["id"], quantity=1, service_type="DELIVERY", payment_method="CASH", delivery_address="Rua A, 1")
    assert no_zone.status_code == 422 and "bairro" in no_zone.json()["detail"]
    ok = shop.public_order(product["id"], quantity=1, service_type="DELIVERY", payment_method="CASH", delivery_address="Rua A, 1", delivery_zone="jardim")
    assert ok.status_code == 201 and Decimal(ok.json()["total"]) == Decimal("39.50")
    tracked = shop.public_get(f"/public/orders/{ok.json()['public_token']}").json()
    assert tracked["delivery_address"] == "Rua A, 1 · Jardim"
    assert shop.patch("/tenant/settings", {"delivery_zones": [{"name": "A", "fee": "1"}]}).status_code == 422  # too short
    assert shop.patch("/tenant/settings", {"delivery_zones": [{"name": "Centro", "fee": "1"}, {"name": "centro", "fee": "2"}]}).status_code == 422


def test_pix_up_front_for_deliveries(make_tenant):
    shop = make_tenant()
    product = _store(shop, require_pix_delivery=True)
    cash = shop.public_order(product["id"], service_type="DELIVERY", payment_method="CASH", delivery_address="Rua B, 2")
    assert cash.status_code == 422 and "PIX" in cash.json()["detail"]
    number = shop.public_order(product["id"], service_type="DELIVERY", payment_method="PIX", delivery_address="Rua B, 2").json()["order_number"]
    order = next(o for o in shop.get("/orders").json()["items"] if o["order_number"] == number)
    assert shop.patch(f"/orders/{order['id']}/status", {"status": "PREPARING"}).status_code == 422
    assert shop.patch(f"/orders/{order['id']}/payment", {"payment_status": "PAID"}).json()["status"] == "PREPARING"
    # Requiring PIX without a key makes no sense.
    other = make_tenant()
    assert other.patch("/tenant/settings", {"require_pix_delivery": True}).status_code == 422


def test_customer_cancels_before_the_kitchen_starts(make_tenant):
    shop = make_tenant()
    product = _store(shop)
    token = shop.public_order(product["id"], service_type="TAKEAWAY", payment_method="CASH").json()["public_token"]
    assert shop.public_post(f"/public/orders/{token}/cancel").status_code == 204
    assert shop.public_get(f"/public/orders/{token}").json()["status"] == "CANCELLED"
    number = shop.public_order(product["id"], service_type="TAKEAWAY", payment_method="CASH").json()
    order = next(o for o in shop.get("/orders").json()["items"] if o["order_number"] == number["order_number"])
    shop.patch(f"/orders/{order['id']}/status", {"status": "PREPARING"})
    assert shop.public_post(f"/public/orders/{number['public_token']}/cancel").status_code == 422


def test_store_page_has_its_own_link_preview(make_tenant, monkeypatch):
    from app.core.config import settings
    from app.web import web
    shop = make_tenant()
    shop.patch("/tenant/settings", {"description": "Os melhores pães da cidade"})
    monkeypatch.setattr(settings, "root_domain", "mesadig.test")
    browser = TestClient(web)
    page = browser.get("/", headers={"host": f"{shop.slug}.mesadig.test"}).text
    assert f"/og/{shop.slug}.jpg" in page and "Os melhores pães da cidade" in page and page.count('name="description"') == 1
    image = browser.get(f"/og/{shop.slug}.jpg")
    assert image.status_code == 200 and image.headers["content-type"] == "image/jpeg"
    assert "og-image.jpg" in browser.get("/", headers={"host": "mesadig.test"}).text
