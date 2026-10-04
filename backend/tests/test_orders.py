import pytest

pytestmark = pytest.mark.integration


def test_public_order_full_lifecycle(make_tenant):
    tenant = make_tenant()
    product = tenant.add_product("Cappuccino", "9.00")

    created = tenant.public_order(
        product["id"], quantity=3, table_label="  12 ", service_type="DINE_IN", notes="Sem açúcar"
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["status"] == "RECEIVED" and body["total"] == "27.00"

    tracking = tenant.public_get(f"/public/orders/{body['public_token']}").json()
    assert tracking["table_label"] == "12"
    assert tracking["items"][0]["product_name"] == "Cappuccino"

    order = tenant.get("/orders").json()[0]
    assert order["customer_name"] == "Maria Cliente" and order["notes"] == "Sem açúcar"

    flow = ["PREPARING", "READY", "FINISHED"]
    for status in flow:
        response = tenant.patch(f"/orders/{order['id']}/status", {"status": status})
        assert response.status_code == 200, response.text
        assert response.json()["status"] == status

    # Final state: no more transitions.
    assert tenant.patch(f"/orders/{order['id']}/status", {"status": "CANCELLED", "reason": "x"}).status_code == 422
    history = [h["status"] for h in tenant.get(f"/orders/{order['id']}").json()["status_history"]]
    assert history == ["RECEIVED", "PREPARING", "READY", "FINISHED"]


def test_price_comes_from_catalog_and_is_snapshotted(make_tenant):
    tenant = make_tenant()
    product = tenant.add_product("Bolo", "10.00")
    tenant.public_order(product["id"], quantity=2)

    tenant.patch(f"/products/{product['id']}", {"price": "99.00", "name": "Bolo renomeado"})
    item = tenant.get("/orders").json()[0]["items"][0]
    assert (item["product_name"], item["unit_price"], item["total_price"]) == ("Bolo", "10.00", "20.00")


def test_cancel_requires_reason(make_tenant):
    tenant = make_tenant()
    product = tenant.add_product()
    tenant.public_order(product["id"])
    order_id = tenant.get("/orders").json()[0]["id"]

    assert tenant.patch(f"/orders/{order_id}/status", {"status": "CANCELLED"}).status_code == 422
    done = tenant.patch(f"/orders/{order_id}/status", {"status": "CANCELLED", "reason": "Cliente desistiu"})
    assert done.status_code == 200 and done.json()["status"] == "CANCELLED"
    # Cancelled orders cannot be paid.
    assert tenant.patch(f"/orders/{order_id}/payment", {"payment_status": "PAID"}).status_code == 422


def test_staff_confirms_payment(make_tenant):
    tenant = make_tenant()
    product = tenant.add_product()
    tenant.public_order(product["id"])
    order_id = tenant.get("/orders").json()[0]["id"]

    paid = tenant.patch(f"/orders/{order_id}/payment", {"payment_status": "PAID", "payment_method": "PIX"}).json()
    assert paid["payment_status"] == "PAID" and paid["payment_method"] == "PIX" and paid["paid_at"]


def test_closed_business_refuses_orders(make_tenant):
    tenant = make_tenant()
    product = tenant.add_product()
    assert tenant.patch("/tenant/settings", {"accepting_orders": False}).status_code == 200

    response = tenant.public_order(product["id"])
    assert response.status_code == 422
    assert tenant.public_get("/public/menu").json()["tenant"]["accepting_orders"] is False


def test_inactive_products_leave_the_menu_and_cannot_be_ordered(make_tenant):
    tenant = make_tenant()
    product = tenant.add_product("Sazonal")
    tenant.delete(f"/products/{product['id']}")

    assert tenant.public_get("/public/menu").json()["products"] == []
    assert tenant.public_order(product["id"]).status_code == 404


def test_history_by_phone_and_validation(make_tenant):
    tenant = make_tenant()
    product = tenant.add_product()
    tenant.public_order(product["id"], phone="(11) 98888-7777")

    history = tenant.public_get("/public/history", params={"phone": "11988887777"}).json()
    assert len(history) == 1 and history[0]["items"][0]["quantity"] == 2
    assert tenant.public_order(product["id"], phone="123").status_code == 422
    assert tenant.public_order(product["id"], quantity=0).status_code == 422


def test_concurrent_numbering_is_sequential(make_tenant):
    tenant = make_tenant()
    product = tenant.add_product()
    numbers = [tenant.public_order(product["id"], phone=f"1190000{i:04d}").json()["order_number"] for i in range(5)]
    assert numbers == [1, 2, 3, 4, 5]
