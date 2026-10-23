"""Service fee is optional (tip) and promotions need the customer's consent (LGPD)."""
from decimal import Decimal


def _setup(shop, tabs=False):
    shop.patch("/tenant/settings", {"service_fee_percent": "10", "tabs_enabled": tabs, "tabs_auto_approve": True,
                                    "enabled_services": ["DINE_IN", "TAKEAWAY"]})
    return shop.add_product(price="50.00")


def test_customer_can_remove_the_service_fee(make_tenant):
    shop = make_tenant()
    product = _setup(shop)
    with_fee = shop.public_order(product["id"], quantity=1, service_type="DINE_IN", table_label="3", payment_method="CASH").json()
    without = shop.public_order(product["id"], quantity=1, service_type="DINE_IN", table_label="3", payment_method="CASH", waive_service_fee=True).json()
    assert Decimal(with_fee["total"]) == Decimal("55.00") and Decimal(without["total"]) == Decimal("50.00")


def test_table_bill_fee_can_be_removed_and_put_back(make_tenant):
    shop = make_tenant()
    product = _setup(shop, tabs=True)
    code = shop.table_code("7")
    order = shop.public_order(product["id"], quantity=2, service_type="DINE_IN", table_label="7", table_code=code, payment_method="TAB").json()
    token = order["tab_token"]
    assert Decimal(shop.public_get(f"/public/tabs/{token}").json()["totals"]["total"]) == Decimal("110.00")
    tab = shop.public_post(f"/public/tabs/{token}/service-fee", {"waived": True}).json()
    assert tab["service_fee_waived"] is True and Decimal(tab["totals"]["total"]) == Decimal("100.00")
    # New rounds on a bill without fee stay without fee.
    shop.public_order(product["id"], quantity=1, service_type="DINE_IN", table_label="7", table_code=code, payment_method="TAB")
    assert Decimal(shop.public_get(f"/public/tabs/{token}").json()["totals"]["service_fee"]) == Decimal("0.00")
    tab = shop.public_post(f"/public/tabs/{token}/service-fee", {"waived": False}).json()
    assert Decimal(tab["totals"]["total"]) == Decimal("165.00")


def test_marketing_consent_comes_only_from_the_customer(make_tenant):
    shop = make_tenant()
    product = _setup(shop)
    shop.public_order(product["id"], phone="11955550001", service_type="TAKEAWAY", payment_method="CASH", marketing_opt_in=True)
    shop.public_order(product["id"], phone="11955550002", service_type="TAKEAWAY", payment_method="CASH")
    customers = {c["phone"]: c for c in shop.get("/customers").json()["items"]}
    yes, no = customers["11955550001"], customers["11955550002"]
    assert yes["marketing_opt_in"] is True and no["marketing_opt_in"] is False
    assert shop.patch(f"/customers/{no['id']}", {"marketing_opt_in": True}).status_code == 422  # staff cannot opt someone in
    assert shop.patch(f"/customers/{yes['id']}", {"marketing_opt_in": False}).json()["marketing_opt_in"] is False
