"""Advanced analytics (plan Profissional, and the trial)."""
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update

from app.core.database import SessionLocal
from app.models.customer import Customer
from app.models.order import Order


def _order(shop, product_id, phone, name="Cliente"):
    response = shop.public_order(product_id, customer_name=name, phone=phone, quantity=1, service_type="TAKEAWAY", payment_method="PIX")
    assert response.status_code == 201, response.text
    return response.json()


def test_insights_are_only_for_the_professional_plan(make_tenant):
    assert make_tenant(plan="essencial").get("/analytics/insights").status_code == 402
    pro = make_tenant(plan="pro")
    assert pro.get("/analytics/insights").status_code == 200
    names = pro.get("/platform/plans").json()["plans"]
    assert "insights" in next(p for p in names if p["key"] == "pro")["features"]
    assert "insights" not in next(p for p in names if p["key"] == "essencial")["features"]


def test_returning_customers_abc_and_win_back_list(make_tenant):
    shop = make_tenant(plan="pro")
    burger = shop.add_product(name="Burger", price="40.00")
    water = shop.add_product(name="Água", price="4.00")
    _order(shop, burger["id"], "11911110001", "Fiel")
    _order(shop, burger["id"], "11911110001", "Fiel")
    _order(shop, water["id"], "11911110002", "Novo")
    # A regular who stopped coming: two orders, the last one 40 days ago.
    for _ in range(2):
        _order(shop, burger["id"], "11911110003", "Sumido")
    for _ in range(2):
        _order(shop, burger["id"], "11911110004", "Sumido sem consentimento")
    with SessionLocal() as db:
        lost = select(Customer.id).where(Customer.phone_digits.in_(["11911110003", "11911110004"]))
        db.execute(update(Order).where(Order.customer_id.in_(lost)).values(created_at=datetime.now(timezone.utc) - timedelta(days=40)))
        db.execute(update(Customer).where(Customer.phone_digits == "11911110003").values(marketing_opt_in=True))
        db.commit()

    data = shop.get("/analytics/insights", params={"period": "all"}).json()
    assert data["kpis"]["customers"] == 4 and data["kpis"]["new_customers"] == 1  # only "Novo" bought once
    grades = {p["product_name"]: p["grade"] for p in data["abc"]}
    assert grades["Burger"] == "A" and grades["Água"] in ("B", "C")
    # LGPD: only the customer who agreed to promotions is listed; the other is just counted.
    assert [c["name"] for c in data["at_risk"]] == ["Sumido"] and data["at_risk"][0]["days_since"] >= 39
    assert data["lapsed_without_consent"] == 1
    assert data["top_customers"][0]["name"] in ("Fiel", "Sumido")
    assert len(data["heatmap"]) >= 1


def test_month_has_projection_and_comparison(make_tenant):
    shop = make_tenant(plan="pro")
    product = shop.add_product(price="25.00")
    _order(shop, product["id"], "11911110009")
    data = shop.get("/analytics/insights").json()
    assert data["comparison"] and data["comparison"][0]["day"] == 1
    if datetime.now().day > 1:
        assert data["kpis"]["projected_revenue"] is not None
