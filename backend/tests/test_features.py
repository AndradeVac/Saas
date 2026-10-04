import io
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest
from PIL import Image

from tests.conftest import PASSWORD

pytestmark = pytest.mark.integration


def png_bytes(size=(1600, 900), color=(200, 80, 20)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, color).save(buffer, format="PNG")
    return buffer.getvalue()


# ---- options -------------------------------------------------------------------------------
PIZZA_OPTIONS = [
    {"id": "size", "name": "Tamanho", "required": True, "min": 1, "max": 1,
     "options": [{"id": "m", "name": "Média", "price": "0"}, {"id": "g", "name": "Grande", "price": "10.00"}]},
    {"id": "extra", "name": "Adicionais", "required": False, "min": 0, "max": 2,
     "options": [{"id": "queijo", "name": "Queijo extra", "price": "4.00"}, {"id": "bacon", "name": "Bacon", "price": "5.00"}]},
]


def test_options_are_validated_and_priced(make_tenant):
    tenant = make_tenant()
    pizza = tenant.add_product("Pizza", "40.00", options=PIZZA_OPTIONS)
    pid = pizza["id"]

    def order(options, quantity=1):
        return tenant.public_order(pid, quantity=quantity, items_options=options)

    # missing required group / unknown option / too many
    assert order([]).status_code == 422
    assert order([{"group_id": "size", "option_id": "zzz"}]).status_code == 422
    too_many = [{"group_id": "size", "option_id": "m"}] + [
        {"group_id": "extra", "option_id": o} for o in ("queijo", "bacon")
    ]
    assert order(too_many).status_code == 201  # 2 extras allowed
    assert order(too_many + [{"group_id": "extra", "option_id": "queijo"}]).status_code == 422  # repeated

    created = order([{"group_id": "size", "option_id": "g"}, {"group_id": "extra", "option_id": "bacon"}], quantity=2)
    assert created.status_code == 201
    assert created.json()["total"] == "110.00"  # (40 + 10 + 5) * 2
    item = tenant.get("/orders").json()["items"][0]["items"][0]
    assert item["unit_price"] == "55.00"
    assert [o["name"] for o in item["options"]] == ["Grande", "Bacon"]


def test_option_group_validation(make_tenant):
    tenant = make_tenant()
    bad = {"category_id": tenant.category_id(), "name": "X", "price": "1",
           "options": [{"name": "G", "min": 3, "max": 2, "options": [{"name": "a"}]}]}
    assert tenant.post("/products", bad).status_code == 422


def test_sold_out_product_stays_visible_but_cannot_be_ordered(make_tenant):
    tenant = make_tenant()
    product = tenant.add_product("Torta")
    tenant.patch(f"/products/{product['id']}", {"available": False})
    menu_product = tenant.public_get("/public/menu").json()["products"][0]
    assert menu_product["available"] is False
    assert tenant.public_order(product["id"]).status_code == 422


# ---- fees, services, payments -----------------------------------------------------------------
def test_service_fee_delivery_fee_and_rules(make_tenant):
    tenant = make_tenant()
    product = tenant.add_product("Prato", "50.00")
    assert tenant.patch("/tenant/settings", {
        "service_fee_percent": "10", "delivery_fee": "7.50", "min_order_value": "20",
        "enabled_services": ["DINE_IN", "DELIVERY"], "accepted_payments": ["CASH", "PIX"],
    }).status_code == 200

    dine_in = tenant.public_order(product["id"], quantity=1, table_label="3").json()
    assert dine_in["total"] == "55.00"  # 50 + 10% service

    assert tenant.public_order(product["id"], quantity=1, service_type="DELIVERY").status_code == 422  # address required
    delivery = tenant.public_order(product["id"], quantity=1, service_type="DELIVERY", delivery_address="Rua A, 10")
    assert delivery.json()["total"] == "57.50"  # no service fee on delivery

    assert tenant.public_order(product["id"], quantity=1, service_type="TAKEAWAY").status_code == 422  # not enabled
    assert tenant.public_order(product["id"], quantity=1, payment_method="CARD").status_code == 422  # not accepted

    cheap = tenant.add_product("Bala", "5.00")
    assert tenant.public_order(cheap["id"], quantity=1).status_code == 422  # below minimum


# ---- opening hours -------------------------------------------------------------------------------
def test_schedule_mode_closes_outside_hours(make_tenant):
    tenant = make_tenant()
    product = tenant.add_product()
    assert tenant.patch("/tenant/settings", {"hours_mode": "SCHEDULE"}).status_code == 422  # needs hours

    now = datetime.now(timezone.utc)
    day = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
    # An interval that certainly does not contain "now" in any time zone: today, 1 minute long, 12h away.
    settings = tenant.get("/tenant/settings").json()
    assert settings["timezone"] == "America/Sao_Paulo"
    from zoneinfo import ZoneInfo
    local = now.astimezone(ZoneInfo("America/Sao_Paulo"))
    away = (local + timedelta(hours=12)).replace(second=0, microsecond=0)
    hours = {day[away.weekday()]: [[away.strftime("%H:%M"), (away + timedelta(minutes=1)).strftime("%H:%M")]]}
    assert tenant.patch("/tenant/settings", {"hours_mode": "SCHEDULE", "opening_hours": hours}).status_code == 200

    menu = tenant.public_get("/public/menu").json()["tenant"]
    assert menu["is_open"] is False and menu["accepting_orders"] is True
    assert tenant.public_order(product["id"]).status_code == 422

    all_day = {d: [["00:00", "23:59"]] for d in day}
    tenant.patch("/tenant/settings", {"opening_hours": all_day})
    assert tenant.public_get("/public/menu").json()["tenant"]["is_open"] is True
    assert tenant.public_order(product["id"]).status_code == 201

    assert tenant.patch("/tenant/settings", {"opening_hours": {"mon": [["25:00", "26:00"]]}}).status_code == 422


# ---- coupons -------------------------------------------------------------------------------------
def test_coupon_lifecycle(make_tenant):
    tenant = make_tenant()
    product = tenant.add_product("Bolo", "20.00")
    created = tenant.post("/coupons", {"code": "bem vindo10", "kind": "PERCENT", "value": "10", "max_uses": 1})
    assert created.status_code == 201 and created.json()["code"] == "BEMVINDO10"
    assert tenant.post("/coupons", {"code": "BEMVINDO10", "kind": "FIXED", "value": "5"}).status_code == 422
    assert tenant.post("/coupons", {"code": "OVER", "kind": "PERCENT", "value": "150"}).status_code == 422

    check = tenant.public_post("/public/coupons/check", {"code": "bemvindo10", "subtotal": "40.00"})
    assert check.status_code == 200 and check.json()["discount"] == "4.00"
    assert tenant.public_post("/public/coupons/check", {"code": "NOPE", "subtotal": "40"}).status_code == 422

    order = tenant.public_order(product["id"], quantity=2, coupon_code="BEMVINDO10")
    assert order.status_code == 201 and order.json()["total"] == "36.00"
    # single-use coupon is now spent
    assert tenant.public_order(product["id"], coupon_code="BEMVINDO10", phone="11977776666").status_code == 422

    # cancelling gives the use back
    order_id = tenant.get("/orders").json()["items"][0]["id"]
    tenant.patch(f"/orders/{order_id}/status", {"status": "CANCELLED", "reason": "teste"})
    assert tenant.public_order(product["id"], coupon_code="BEMVINDO10", phone="11977776666").status_code == 201


def test_coupon_last_use_is_atomic(make_tenant):
    tenant = make_tenant()
    product = tenant.add_product("Bolo", "20.00")
    tenant.post("/coupons", {"code": "UNICO", "kind": "FIXED", "value": "5", "max_uses": 1})

    def place(i):
        return tenant.public_order(product["id"], coupon_code="UNICO", phone=f"1190000{i:04d}").status_code

    with ThreadPoolExecutor(max_workers=4) as pool:
        codes = list(pool.map(place, range(4)))
    assert sorted(codes) == [201, 422, 422, 422]


def test_coupons_are_isolated(make_tenant):
    first, second = make_tenant(), make_tenant()
    first.post("/coupons", {"code": "SECRETO", "kind": "FIXED", "value": "5"})
    assert second.get("/coupons").json() == []
    assert second.public_post("/public/coupons/check", {"code": "SECRETO", "subtotal": "50"}).status_code == 422


# ---- media -----------------------------------------------------------------------------------------
def test_image_upload_is_resized_served_and_cleaned_up(make_tenant, client):
    tenant = make_tenant()
    upload = client.post(
        "/media", files={"file": ("foto.png", png_bytes(), "image/png")}, headers=tenant.auth_headers,
    )
    assert upload.status_code == 201, upload.text
    url = upload.json()["url"]

    served = client.get(url)  # public, no headers
    assert served.status_code == 200 and served.headers["content-type"] == "image/webp"
    assert "immutable" in served.headers["cache-control"]
    image = Image.open(io.BytesIO(served.content))
    assert max(image.size) <= 1200

    product = tenant.add_product("Com foto", image_url=url)
    assert tenant.public_get("/public/menu").json()["products"][0]["image_url"] == url

    # replacing the image removes the old file
    tenant.patch(f"/products/{product['id']}", {"image_url": None})
    assert client.get(url).status_code == 404


def test_upload_rejects_non_images_and_non_admins(make_tenant, client):
    tenant = make_tenant()
    bad = client.post("/media", files={"file": ("x.png", b"not an image", "image/png")}, headers=tenant.auth_headers)
    assert bad.status_code == 422
    assert client.post("/media", files={"file": ("x.png", png_bytes((10, 10)), "image/png")}).status_code == 401

    tenant.post("/users", {"name": "Op", "email": f"op@{tenant.slug}.com", "password": PASSWORD})
    operator = type(tenant)(client, tenant.slug, f"op@{tenant.slug}.com")
    operator.login()
    assert client.post("/media", files={"file": ("x.png", png_bytes((10, 10)), "image/png")}, headers=operator.auth_headers).status_code == 403


def test_image_urls_must_be_safe(make_tenant):
    tenant = make_tenant()
    assert tenant.patch("/tenant/settings", {"logo_url": "javascript:alert(1)"}).status_code == 422
    assert tenant.post("/products", {"category_id": tenant.category_id(), "name": "X", "price": "1", "image_url": "data:text/html,x"}).status_code == 422
    assert tenant.patch("/tenant/settings", {"logo_url": "https://exemplo.com/logo.png"}).status_code == 200


# ---- customers & orders listing ---------------------------------------------------------------------
def test_customers_search_stats_and_unique_phone(make_tenant):
    tenant = make_tenant()
    product = tenant.add_product("Café", "6.00")
    tenant.public_order(product["id"], quantity=2, phone="11911112222")
    tenant.public_order(product["id"], quantity=1, phone="(11) 91111-2222")  # same customer, different format
    tenant.public_order(product["id"], quantity=1, phone="21933334444")

    listing = tenant.get("/customers", params={"sort": "spent"}).json()
    assert listing["total"] == 2
    top = listing["items"][0]
    assert top["orders_count"] == 2 and top["total_spent"] == "18.00"

    assert tenant.get("/customers", params={"q": "3334"}).json()["total"] == 1
    assert tenant.get("/customers", params={"q": "maria"}).json()["total"] == 2
    assert tenant.get("/customers", params={"page_size": 1, "page": 2}).json()["items"].__len__() == 1

    other = tenant.post("/customers", {"name": "Manual", "phone": "11 90000-0000"}).json()
    dup = tenant.post("/customers", {"name": "Dup", "phone": "11900000000"})
    assert dup.status_code == 422
    assert tenant.patch(f"/customers/{other['id']}", {"phone": "11911112222"}).status_code == 422
    assert tenant.get("/customers/export").status_code == 200


def test_orders_filters_board_and_export(make_tenant):
    tenant = make_tenant()
    product = tenant.add_product("Pão", "2.00")
    for i in range(3):
        tenant.public_order(product["id"], phone=f"1190000{i:04d}", table_label=str(i + 1))
    first = tenant.get("/orders").json()["items"][-1]
    tenant.patch(f"/orders/{first['id']}/status", {"status": "CANCELLED", "reason": "x"})

    assert tenant.get("/orders", params={"status": "CANCELLED"}).json()["total"] == 1
    assert tenant.get("/orders", params={"status": ["RECEIVED", "PREPARING"]}).json()["total"] == 2
    assert tenant.get("/orders", params={"q": f"#{first['order_number']}"}).json()["total"] == 1
    assert tenant.get("/orders", params={"payment_status": "PAID"}).json()["total"] == 0
    page = tenant.get("/orders", params={"page_size": 2}).json()
    assert page["total"] == 3 and len(page["items"]) == 2

    today = datetime.now().date().isoformat()
    assert tenant.get("/orders", params={"date_from": today, "date_to": today}).json()["total"] == 3
    assert tenant.get("/orders", params={"date_from": "2001-01-01", "date_to": "2001-01-02"}).json()["total"] == 0

    assert len(tenant.get("/orders/board").json()) == 3
    export = tenant.get("/orders/export")
    assert export.status_code == 200 and export.text.count("\n") == 4  # header + 3 rows

    edited = tenant.patch(f"/orders/{tenant.get('/orders').json()['items'][0]['id']}", {"table_label": "9", "notes": "sem sal"})
    assert edited.status_code == 200 and edited.json()["table_label"] == "9"
    assert tenant.patch(f"/orders/{first['id']}", {"notes": "x"}).status_code == 422  # cancelled


# ---- team ------------------------------------------------------------------------------------------
def test_team_management(make_tenant, client):
    tenant = make_tenant()
    staff = tenant.post("/users", {"name": "Ana", "email": f"ana@{tenant.slug}.com", "password": PASSWORD}).json()

    renamed = tenant.patch(f"/users/{staff['id']}", {"name": "Ana Paula", "role": "ADMIN"}).json()
    assert renamed["name"] == "Ana Paula" and renamed["role"] == "ADMIN"

    me = tenant.get("/auth/me").json()
    tenant.patch(f"/users/{staff['id']}", {"role": "OPERATOR"})
    assert tenant.patch(f"/users/{me['id']}", {"role": "OPERATOR"}).status_code == 422  # last admin

    assert tenant.post(f"/users/{staff['id']}/password", {"new_password": "outra-senha-123"}).status_code == 204
    ana = type(tenant)(client, tenant.slug, f"ana@{tenant.slug}.com")
    assert ana.login(password=PASSWORD).status_code == 401
    assert ana.login(password="outra-senha-123").status_code == 200


def test_audit_is_paginated(make_tenant):
    tenant = make_tenant()
    for i in range(3):
        tenant.add_product(f"P{i}")
    page = tenant.get("/audit", params={"page_size": 2, "entity_type": "PRODUCT"}).json()
    assert page["total"] == 3 and len(page["items"]) == 2
