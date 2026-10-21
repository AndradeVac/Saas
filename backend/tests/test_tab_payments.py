"""Fase 1 do pagamento da mesa: PIX com valor exato direto para a chave do restaurante, por pessoa ou inteiro."""
from decimal import Decimal

from app.core.pix import _crc16, brcode, normalize_pix_key


def open_table(shop, label="7", price="20.00", rounds=1):
    shop.patch("/tenant/settings", {"tabs_enabled": True, "tabs_auto_approve": True, "pix_key": "(11) 94930-7879",
                                    "accepted_payments": ["PIX", "CARD", "CASH"], "city": "São Caetano do Sul"})
    product = shop.add_product(price=price)
    code = shop.table_code(label)
    token = None
    for _ in range(rounds):
        token = shop.public_order(product["id"], quantity=1, table_label=label, table_code=code).json()["tab_token"]
    for order in shop.get("/orders/board").json():
        for status in ("PREPARING", "READY"):
            shop.patch(f"/orders/{order['id']}/status", {"status": status})
    return token, shop.get("/tabs").json()[0]["id"]


def test_brcode_format():
    assert _crc16("123456789") == "29B1"
    assert normalize_pix_key("(11) 94930-7879") == "+5511949307879"
    assert normalize_pix_key("529.982.247-25") == "52998224725"
    code = brcode("+5511949307879", Decimal("45.50"), "Padaria Inoviosion", "São Caetano do Sul", "MESA7")
    assert code.startswith("000201") and "br.gov.bcb.pix" in code and "540545.50" in code
    assert "6015SAO CAETANO DO" not in code  # trailing space trimmed after truncation
    assert code[-4:] == _crc16(code[:-4])


def test_split_bill_paid_by_pix_closes_the_table(make_tenant):
    shop = make_tenant()
    token, tab_id = open_table(shop, rounds=2)  # R$ 40,00
    pix = shop.public_get(f"/public/tabs/{token}/pix", params={"amount": "20.00"}).json()
    assert pix["amount"] == "20.00" and "+5511949307879" in pix["code"] and "540520.00" in pix["code"]

    # Ana pays her half and says so; the waiter is alerted, the bill is not paid yet.
    shop.public_post(f"/public/tabs/{token}/pix-report", {"amount": "20.00", "payer_name": "Ana"})
    tab = shop.get(f"/tabs/{tab_id}").json()
    assert tab["alerts"]["payments_to_confirm"] == 1 and tab["totals"]["reported"] == "20.00" and tab["totals"]["paid"] == "0.00"
    ana = tab["payments"][0]["id"]
    tab = shop.post(f"/tabs/{tab_id}/payments/{ana}/confirm").json()
    assert tab["totals"]["paid"] == "20.00" and tab["totals"]["remaining"] == "20.00" and tab["status"] != "CLOSED"

    # Bruno pays cash to the waiter: the bill is settled and closes itself.
    tab = shop.post(f"/tabs/{tab_id}/payments", {"amount": "20.00", "payment_method": "CASH"}).json()
    assert tab["status"] == "CLOSED" and tab["totals"]["remaining"] == "0.00"
    assert shop.get("/tabs").json() == []


def test_rejected_report_and_limits(make_tenant):
    shop = make_tenant()
    token, tab_id = open_table(shop)  # R$ 20,00
    assert shop.public_get(f"/public/tabs/{token}/pix", params={"amount": "25.00"}).status_code == 422
    assert shop.public_post(f"/public/tabs/{token}/pix-report", {"amount": "25.00"}).status_code == 422
    shop.public_post(f"/public/tabs/{token}/pix-report", {"amount": "20.00", "payer_name": "Golpista"})
    payment = shop.get(f"/tabs/{tab_id}").json()["payments"][0]["id"]
    tab = shop.post(f"/tabs/{tab_id}/payments/{payment}/reject").json()
    assert tab["totals"]["paid"] == "0.00" and tab["status"] != "CLOSED"
    assert shop.post(f"/tabs/{tab_id}/payments/{payment}/confirm").status_code == 422  # already resolved

    # Closing pays whatever is left with the chosen method.
    closed = shop.post(f"/tabs/{tab_id}/close", {"payment_method": "CARD"}).json()
    assert closed["status"] == "CLOSED" and closed["totals"]["paid"] == "20.00"


def test_no_pix_key_means_no_pix_code(make_tenant):
    shop = make_tenant()
    token, _ = open_table(shop)
    shop.patch("/tenant/settings", {"pix_key": None})
    response = shop.public_get(f"/public/tabs/{token}/pix")
    assert response.status_code == 422 and "garçom" in response.json()["detail"]
