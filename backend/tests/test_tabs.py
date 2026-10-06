"""Comanda por mesa: dine-in orders pile up on the table's bill and are paid once, when the table closes."""
from datetime import datetime, timedelta, timezone

from sqlalchemy import update

from app.core.database import SessionLocal
from app.models.tab import Tab


def enable_tabs(shop, **extra):
    response = shop.patch("/tenant/settings", {"tabs_enabled": True, "min_order_value": "30.00", **extra})
    assert response.status_code == 200, response.text


def advance(shop, order_id, *statuses):
    for status in statuses:
        assert shop.patch(f"/orders/{order_id}/status", {"status": status}).status_code == 200


def board_ids(shop):
    return {order["id"] for order in shop.get("/orders/board").json()}


def order_id(shop, number):
    return next(o["id"] for o in shop.get("/orders/board").json() if o["order_number"] == number)


def test_full_table_flow(make_tenant):
    shop = make_tenant()
    enable_tabs(shop)
    beer = shop.add_product("Chope", "12.00")

    # First phone at table 7: the bill opens waiting for approval, and the kitchen does not see it yet.
    first = shop.public_order(beer["id"], quantity=1, table_label="7", payment_method="PIX")
    assert first.status_code == 201, first.text
    token = first.json()["tab_token"]
    assert token
    tabs = shop.get("/tabs").json()
    assert len(tabs) == 1 and tabs[0]["status"] == "PENDING" and tabs[0]["alerts"]["needs_approval"]
    assert board_ids(shop) == set()

    assert shop.post(f"/tabs/{tabs[0]['id']}/approve").json()["status"] == "OPEN"
    first_id = order_id(shop, first.json()["order_number"])
    order = shop.get(f"/orders/{first_id}").json()
    assert order["payment_method"] == "TAB" and order["tab_id"] == tabs[0]["id"]

    # A second phone at the same table finds the bill and joins it; the minimum order does not apply per round.
    assert shop.public_get("/public/tables/7/tab").json()["public_token"] == token
    second = shop.public_order(beer["id"], quantity=1, phone="11977776666", table_label="7")
    assert second.status_code == 201 and second.json()["tab_token"] == token
    bill = shop.public_get(f"/public/tabs/{token}").json()
    assert len(bill["orders"]) == 2 and bill["totals"]["total"] == "24.00"

    # Paying an order alone is not possible: it belongs to the bill.
    assert shop.patch(f"/orders/{first_id}/payment", {"payment_status": "PAID"}).status_code == 422

    # Customer asks for the bill, split in two; ordering again reopens it (automation).
    closing = shop.public_post(f"/public/tabs/{token}/close-request", {"payment_method": "PIX", "split_count": 2}).json()
    assert closing["status"] == "CLOSING" and closing["totals"]["per_person"] == "12.00"
    assert shop.get("/tabs").json()[0]["alerts"]["wants_to_close"]
    third = shop.public_order(beer["id"], quantity=1, table_label="7")
    assert shop.public_get(f"/public/tabs/{token}").json()["status"] == "OPEN"

    # Staff closes: blocked while something is still cooking.
    tab_id = tabs[0]["id"]
    assert shop.post(f"/tabs/{tab_id}/close", {"payment_method": "CARD"}).status_code == 422
    for number in (first.json()["order_number"], second.json()["order_number"], third.json()["order_number"]):
        advance(shop, order_id(shop, number), "PREPARING", "READY")
    closed = shop.post(f"/tabs/{tab_id}/close", {"payment_method": "CARD"}).json()
    assert closed["status"] == "CLOSED" and closed["totals"]["total"] == "36.00"
    paid = shop.get(f"/orders/{first_id}").json()
    assert paid["status"] == "FINISHED" and paid["payment_status"] == "PAID" and paid["payment_method"] == "CARD"
    assert shop.get("/tabs").json() == []

    # The table is free: the next customer starts a new bill.
    again = shop.public_order(beer["id"], quantity=1, table_label="7")
    assert again.json()["tab_token"] != token
    assert shop.get("/tabs").json()[0]["number"] == 2


def test_rejecting_a_table_cancels_its_orders(make_tenant):
    shop = make_tenant()
    enable_tabs(shop)
    product = shop.add_product()
    shop.public_order(product["id"], table_label="12")
    tab = shop.get("/tabs").json()[0]
    assert shop.post(f"/tabs/{tab['id']}/cancel", {"reason": "Mesa vazia"}).json()["status"] == "CANCELLED"
    history = shop.get("/orders").json()["items"]
    assert history[0]["status"] == "CANCELLED"


def test_auto_approve_staff_orders_and_rules(make_tenant):
    shop = make_tenant()
    enable_tabs(shop, tabs_auto_approve=True)
    product = shop.add_product()
    assert shop.public_order(product["id"], table_label="3").status_code == 201
    assert shop.get("/tabs").json()[0]["status"] == "OPEN"

    # Dine-in with tabs on needs a table; "TAB" is never a payment the customer can pick otherwise.
    no_table = shop.public_order(product["id"])
    assert no_table.status_code == 422 and "mesa" in no_table.json()["detail"]
    takeaway = shop.public_order(product["id"], service_type="TAKEAWAY", payment_method="TAB")
    assert takeaway.status_code == 422
    assert shop.patch("/tenant/settings", {"accepted_payments": ["TAB"]}).status_code == 422
    assert shop.public_post("/public/tabs/" + shop.get("/tabs").json()[0]["public_token"] + "/close-request",
                            {"payment_method": "TAB"}).status_code == 422

    # Takeaway keeps paying per order (and the minimum order still applies to it).
    assert shop.public_order(product["id"], service_type="TAKEAWAY", payment_method="PIX").status_code == 422
    paid_now = shop.public_order(product["id"], quantity=10, service_type="TAKEAWAY", payment_method="PIX")
    assert paid_now.status_code == 201 and paid_now.json()["tab_token"] is None


def test_alerts_for_idle_tables_and_late_orders(make_tenant):
    shop = make_tenant()
    enable_tabs(shop, tabs_auto_approve=True, tab_idle_minutes=15)
    product = shop.add_product()
    order = shop.public_order(product["id"], table_label="5").json()
    tab = shop.get("/tabs").json()[0]
    assert tab["alerts"]["idle"] is False and tab["alerts"]["late_orders"] == 0

    an_hour_ago = datetime.now(timezone.utc) - timedelta(minutes=60)
    with SessionLocal() as db:
        db.execute(update(Tab).where(Tab.id == tab["id"]).values(last_order_at=an_hour_ago, created_at=an_hour_ago))
        from app.models.order import Order
        db.execute(update(Order).where(Order.tab_id == tab["id"]).values(created_at=an_hour_ago))
        db.commit()
    alerts = shop.get("/tabs").json()[0]["alerts"]
    assert alerts["late_orders"] == 1 and alerts["idle"] is False  # still cooking: not idle yet
    advance(shop, order_id(shop, order["order_number"]), "PREPARING", "READY")
    alerts = shop.get("/tabs").json()[0]["alerts"]
    assert alerts["idle"] is True and alerts["late_orders"] == 0 and alerts["minutes_open"] >= 59


def test_tabs_are_isolated(make_tenant):
    shop, other = make_tenant("a"), make_tenant("b")
    enable_tabs(shop, tabs_auto_approve=True)
    product = shop.add_product()
    token = shop.public_order(product["id"], table_label="1").json()["tab_token"]
    tab_id = shop.get("/tabs").json()[0]["id"]
    assert other.public_get(f"/public/tabs/{token}").status_code == 404
    assert other.get(f"/tabs/{tab_id}").status_code == 404
    assert other.post(f"/tabs/{tab_id}/close", {"payment_method": "CASH"}).status_code == 404
    assert other.get("/tabs").json() == []
