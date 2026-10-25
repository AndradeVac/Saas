"""Regression tests for the QA security findings (2026-10-21)."""
import csv
import io
import uuid

from app.core.client_ip import client_ip
from app.core.rate_limit import login_rate_limit, slug_check_rate_limit
from app.core.tables import normalize_table_label
from tests.conftest import PASSWORD


class _Request:
    def __init__(self, headers: dict, peer: str = "10.0.0.1"):
        self.headers = {k.lower(): v for k, v in headers.items()}
        self.client = type("Peer", (), {"host": peer})()


def test_client_ip_ignores_forged_headers():
    # X-Forwarded-For from the visitor is never trusted.
    assert client_ip(_Request({"X-Forwarded-For": "1.2.3.4"})) == "10.0.0.1"
    # Behind Fly: Fly-Client-IP is the peer Fly saw.
    assert client_ip(_Request({"Fly-Client-IP": "200.1.1.1", "CF-Connecting-IP": "9.9.9.9"})) == "200.1.1.1"
    # CF-Connecting-IP only counts when the request really came through Cloudflare.
    assert client_ip(_Request({"Fly-Client-IP": "172.68.1.10", "CF-Connecting-IP": "177.1.2.3"})) == "177.1.2.3"
    assert client_ip(_Request({"Fly-Client-IP": "172.68.1.10", "CF-Connecting-IP": "lixo"})) == "172.68.1.10"


def test_login_limit_cannot_be_bypassed_with_forwarded_for(make_tenant, client):
    shop = make_tenant()
    login_rate_limit.reset()
    codes = [
        client.post("/auth/login", data={"username": shop.email, "password": f"errada{i}"},
                    headers={**shop.tenant_headers, "X-Forwarded-For": f"10.9.{i}.{i}"}).status_code
        for i in range(12)
    ]
    assert codes[:10] == [401] * 10 and codes[10:] == [429, 429]


def test_platform_limit_ignores_x_tenant(client):
    slug_check_rate_limit.reset()
    codes = [client.get("/platform/slug-available", params={"slug": "qa-livre"}, headers={"X-Tenant": f"t{i}"}).status_code
             for i in range(32)]
    assert codes.count(429) == 2


def test_comanda_requires_the_tables_qr_code(make_tenant):
    shop = make_tenant()
    shop.patch("/tenant/settings", {"tabs_enabled": True, "tabs_auto_approve": True})
    product = shop.add_product()
    code = shop.table_code("9")

    # Without (or with a wrong) code nobody can order on table 9 or read its bill.
    assert shop.public_order(product["id"], table_label="9").status_code == 422
    assert shop.public_order(product["id"], table_label="9", table_code="aaaaaaaa").status_code == 422
    assert shop.public_order(product["id"], table_label="9", table_code=code).status_code == 201
    assert shop.public_get("/public/tables/9/tab").status_code == 404
    assert shop.public_get("/public/tables/9/tab", params={"k": "aaaaaaaa"}).status_code == 404
    assert shop.public_get("/public/tables/9/tab", params={"k": code}).status_code == 200
    # Staff still launch orders for any table without codes.
    staff = shop.post("/orders", {"customer_id": shop.post("/customers", {"name": "Balcão", "phone": "11900001111"}).json()["id"],
                                  "payment_method": "CASH", "service_type": "DINE_IN", "table_label": "9",
                                  "items": [{"product_id": product["id"], "quantity": 1}]})
    assert staff.status_code == 201


def test_codes_are_per_business(make_tenant):
    shop, other = make_tenant("a"), make_tenant("b")
    for t in (shop, other):
        t.patch("/tenant/settings", {"tabs_enabled": True, "tabs_auto_approve": True})
    product = other.add_product()
    assert other.public_order(product["id"], table_label="1", table_code=shop.table_code("1")).status_code == 422


def test_table_labels_are_normalised(make_tenant):
    assert [normalize_table_label(v) for v in ("7", " 07 ", "Mesa 7", "mesa  7", "MESA 07", "Varanda 2", "  ")] == \
        ["7", "7", "7", "7", "7", "Varanda 2", None]
    shop = make_tenant()
    shop.patch("/tenant/settings", {"tabs_enabled": True, "tabs_auto_approve": True})
    product = shop.add_product()
    for label in ("7", "07", "Mesa 7"):
        assert shop.public_order(product["id"], table_label=label, table_code=shop.table_code(label)).status_code == 201
    tabs = shop.get("/tabs").json()
    assert len(tabs) == 1 and tabs[0]["table_label"] == "7" and len(tabs[0]["orders"]) == 3


def test_exports_neutralise_formulas(make_tenant):
    shop = make_tenant()
    product = shop.add_product(price="10.00")
    evil = '=HYPERLINK("http://evil.example/x","Clique")'
    assert shop.public_order(product["id"], customer_name=evil, quantity=1, service_type="TAKEAWAY", payment_method="PIX").status_code == 201
    for path in ("/customers/export", "/orders/export"):
        rows = list(csv.reader(io.StringIO(shop.get(path).content.decode("utf-8-sig")), delimiter=";"))
        cells = [cell for row in rows for cell in row]
        assert "'" + evil in cells and evil not in cells, path


def test_password_change_logs_out_other_sessions(make_tenant, client):
    shop = make_tenant()
    old = dict(shop.auth_headers)
    response = client.post("/auth/password", json={"current_password": PASSWORD, "new_password": "nova-senha-forte"}, headers=old)
    assert response.status_code == 200
    assert client.get("/auth/me", headers=old).status_code == 401
    fresh = {**shop.tenant_headers, "Authorization": f"Bearer {response.json()['access_token']}"}
    assert client.get("/auth/me", headers=fresh).status_code == 200


def test_cancelled_orders_and_rounds_do_not_use_up_the_trial(make_tenant):
    shop = make_tenant(plan=None)
    shop.patch("/tenant/settings", {"tabs_enabled": True, "tabs_auto_approve": True})
    product = shop.add_product()
    code = shop.table_code("4")
    for _ in range(3):  # three rounds on the same table = one comanda
        shop.public_order(product["id"], table_label="4", table_code=code)
    takeaway = shop.public_order(product["id"], service_type="TAKEAWAY", payment_method="PIX").json()
    order_id = next(o["id"] for o in shop.get("/orders/board").json() if o["order_number"] == takeaway["order_number"])
    shop.patch(f"/orders/{order_id}/status", {"status": "CANCELLED", "reason": "spam"})
    assert shop.get("/tenant/plan").json()["usage"]["orders"] == 1


def test_validation_messages_are_portuguese(client, make_tenant):
    shop = make_tenant()
    detail = client.post("/auth/forgot-password", json={"email": "nao-e-email"}, headers=shop.tenant_headers).json()["detail"]
    assert detail[0]["msg"] == "Informe um e-mail válido."
    detail = client.post("/auth/forgot-password", json={}, headers=shop.tenant_headers).json()["detail"]
    assert detail[0]["msg"] == "E-mail: preencha este campo."


def test_rate_limit_is_shared_through_the_database(client):
    """Two app machines must count the same attempts: the counter lives in Postgres."""
    from app.core.rate_limit import RateLimiter
    from fastapi import HTTPException
    from starlette.requests import Request

    limiter = RateLimiter(max_requests=2, window_seconds=60, name="teste-compartilhado")
    other_machine = RateLimiter(max_requests=2, window_seconds=60, name="teste-compartilhado")
    request = Request({"type": "http", "headers": [(b"x-tenant", b"loja"), (b"fly-client-ip", b"203.0.113.9")], "client": ("203.0.113.9", 1)})
    limiter.reset()
    limiter(request)
    other_machine(request)
    try:
        limiter(request)
        raise AssertionError("third attempt should be refused")
    except HTTPException as error:
        assert error.status_code == 429
    limiter.reset()


def test_full_restaurant_on_one_wifi_is_not_blocked(make_tenant, client):
    """30 phones on the same IP polling their comanda every 8 s (~225 reads/min) must keep working."""
    shop = make_tenant()
    codes = {client.get(f"/public/tabs/{uuid.uuid4()}", headers=shop.tenant_headers).status_code for _ in range(240)}
    assert 429 not in codes


def test_coupon_guessing_stays_limited(make_tenant, client):
    shop = make_tenant()
    codes = [client.post("/public/coupons/check", json={"code": f"CUPOM{i}", "subtotal": "50.00"}, headers=shop.tenant_headers).status_code
             for i in range(22)]
    assert codes[-1] == 429 and 429 not in codes[:20]
