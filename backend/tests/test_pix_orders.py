"""PIX QR Code for pickup/delivery orders and PIX key validation in Settings."""
from decimal import Decimal

from app.core.pix import is_valid_pix_key


def test_pix_key_formats():
    for good in ("dono@padaria.com", "63.148.827/0001-67", "(11) 98765-4321", "+5511987654321", "123e4567-e89b-12d3-a456-426614174000"):
        assert is_valid_pix_key(good), good
    for bad in ("abc", "1234", "dono@", "11 9"):
        assert not is_valid_pix_key(bad), bad


def test_settings_reject_invalid_pix_key(make_tenant):
    shop = make_tenant()
    assert shop.patch("/tenant/settings", {"pix_key": "minha chave"}).status_code == 422
    assert shop.patch("/tenant/settings", {"pix_key": "dono@padaria.com"}).status_code == 200
    preview = shop.get("/tenant/pix-preview", params={"key": "dono@padaria.com"})
    assert preview.status_code == 200 and preview.json()["code"].startswith("000201") and Decimal(preview.json()["amount"]) == Decimal("1.00")
    assert shop.get("/tenant/pix-preview", params={"key": "x"}).status_code == 422


def test_pix_order_gets_qr_with_exact_total(make_tenant):
    shop = make_tenant()
    shop.patch("/tenant/settings", {"pix_key": "dono@padaria.com", "accepted_payments": ["PIX", "CASH"]})
    product = shop.add_product(price="23.50")
    order = shop.public_order(product["id"], quantity=2, service_type="TAKEAWAY", payment_method="PIX").json()
    pix = shop.public_get(f"/public/orders/{order['public_token']}/pix")
    assert pix.status_code == 200, pix.text
    assert Decimal(pix.json()["amount"]) == Decimal("47.00") and "540547.00" in pix.json()["code"]  # amount field of the BR Code
    cash = shop.public_order(product["id"], quantity=1, service_type="TAKEAWAY", payment_method="CASH").json()
    assert shop.public_get(f"/public/orders/{cash['public_token']}/pix").status_code == 422
