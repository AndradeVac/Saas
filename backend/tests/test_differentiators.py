"""Loyalty card, product cost/margin, reviews, scheduled orders, menu by time and marketing material."""
from datetime import datetime, time, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import update

from app.core.database import SessionLocal
from app.models.category import Category


def _finish(shop, number):
    order = next(o for o in shop.get("/orders").json()["items"] if o["order_number"] == number)
    for status in ("PREPARING", "READY", "FINISHED"):
        shop.patch(f"/orders/{order['id']}/status", {"status": status})
    return order


def test_loyalty_card_counts_delivered_orders_and_redeems(make_tenant):
    shop = make_tenant()  # pro
    assert shop.patch("/tenant/settings", {"loyalty_enabled": True}).status_code == 422  # needs a reward
    shop.patch("/tenant/settings", {"loyalty_enabled": True, "loyalty_goal": 2, "loyalty_reward": "1 café grátis", "enabled_services": ["TAKEAWAY"]})
    product = shop.add_product(price="10.00")
    tokens = []
    for _ in range(2):
        created = shop.public_order(product["id"], quantity=1, phone="11944440001", service_type="TAKEAWAY", payment_method="CASH").json()
        _finish(shop, created["order_number"])
        tokens.append(created["public_token"])
    card = shop.public_get(f"/public/orders/{tokens[-1]}").json()["loyalty"]
    assert card == {"stamps": 2, "goal": 2, "reward": "1 café grátis", "rewards_available": 1}
    customer = next(c for c in shop.get("/customers").json()["items"] if c["phone"] == "11944440001")
    assert shop.post(f"/customers/{customer['id']}/loyalty/redeem").json()["rewards_available"] == 0
    assert shop.post(f"/customers/{customer['id']}/loyalty/redeem").status_code == 422
    assert make_tenant(plan="essencial").public_get("/tenant").json()["loyalty_enabled"] is False


def test_reviews_once_after_delivery_and_google_invite(make_tenant):
    shop = make_tenant()
    shop.patch("/tenant/settings", {"google_review_url": "https://g.page/r/minha-loja/review", "enabled_services": ["TAKEAWAY"]})
    assert shop.patch("/tenant/settings", {"google_review_url": "g.page/x"}).status_code == 422
    product = shop.add_product(price="10.00")
    created = shop.public_order(product["id"], service_type="TAKEAWAY", payment_method="CASH").json()
    token = created["public_token"]
    assert shop.public_post(f"/public/orders/{token}/review", {"stars": 5}).status_code == 422  # not delivered yet
    _finish(shop, created["order_number"])
    answer = shop.public_post(f"/public/orders/{token}/review", {"stars": 5, "comment": "Muito bom!"})
    assert answer.status_code == 201 and answer.json()["google_review_url"].startswith("https://g.page")
    assert shop.public_post(f"/public/orders/{token}/review", {"stars": 4}).status_code == 422
    assert shop.public_get(f"/public/orders/{token}").json()["review_stars"] == 5
    reviews = shop.get("/analytics/insights", params={"period": "all"}).json()["reviews"]
    assert reviews["count"] == 1 and reviews["average"] == 5 and reviews["latest"][0]["comment"] == "Muito bom!"


def test_product_cost_gives_margin(make_tenant):
    shop = make_tenant()
    shop.patch("/tenant/settings", {"enabled_services": ["TAKEAWAY"]})
    product = shop.add_product(name="Burger", price="30.00", cost="12.00")
    assert shop.get(f"/products/{product['id']}").json()["cost"] == "12.00"
    shop.public_order(product["id"], quantity=2, service_type="TAKEAWAY", payment_method="CASH")
    data = shop.get("/analytics/insights", params={"period": "all"}).json()
    burger = next(p for p in data["abc"] if p["product_name"] == "Burger")
    assert Decimal(burger["profit"]) == Decimal("36.00") and round(burger["margin"], 2) == 0.6
    assert Decimal(data["kpis"]["gross_profit"]) == Decimal("36.00")


def test_scheduled_orders_even_with_the_store_closed(make_tenant):
    shop = make_tenant()
    shop.patch("/tenant/settings", {"enabled_services": ["TAKEAWAY"], "accepting_orders": False})
    product = shop.add_product(price="10.00")
    later = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    assert shop.public_order(product["id"], service_type="TAKEAWAY", payment_method="CASH", scheduled_for=later).status_code == 422  # off
    shop.patch("/tenant/settings", {"scheduling_enabled": True})
    soon = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()
    assert shop.public_order(product["id"], service_type="TAKEAWAY", payment_method="CASH", scheduled_for=soon).status_code == 422
    ok = shop.public_order(product["id"], service_type="TAKEAWAY", payment_method="CASH", scheduled_for=later)
    assert ok.status_code == 201, ok.text
    assert shop.public_get(f"/public/orders/{ok.json()['public_token']}").json()["scheduled_for"] is not None
    assert shop.public_order(product["id"], service_type="TAKEAWAY", payment_method="CASH").status_code == 422  # closed now


def test_category_sold_only_inside_its_time_window(make_tenant):
    shop = make_tenant()
    shop.patch("/tenant/settings", {"enabled_services": ["TAKEAWAY"]})
    product = shop.add_product(price="10.00")
    now = datetime.now(ZoneInfo("America/Sao_Paulo")).time()  # the store's time zone
    closed_from = time((now.hour + 2) % 24, 0)
    closed_until = time((now.hour + 3) % 24, 0)
    with SessionLocal() as db:
        db.execute(update(Category).where(Category.id == product["category_id"]).values(available_from=closed_from, available_until=closed_until))
        db.commit()
    menu = shop.public_get("/public/menu").json()
    assert menu["categories"][0]["available_from"] == closed_from.strftime("%H:%M")
    refused = shop.public_order(product["id"], service_type="TAKEAWAY", payment_method="CASH")
    assert refused.status_code == 422 and "só está disponível" in refused.json()["detail"]


def test_marketing_material(make_tenant):
    shop = make_tenant()
    cards = shop.get("/marketing/table-cards.pdf", params={"labels": ["1", "2", "3"]})
    assert cards.status_code == 200 and cards.content.startswith(b"%PDF")
    assert shop.get("/marketing/poster.pdf").content.startswith(b"%PDF")
    post = shop.get("/marketing/instagram.png")
    assert post.status_code == 200 and post.content[:4] == b"\x89PNG"
