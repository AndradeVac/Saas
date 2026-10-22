"""Error reports must not carry personal data or credentials (LGPD)."""
from app.core.monitoring import _scrub


def test_error_reports_drop_personal_data_and_credentials():
    event = {
        "request": {
            "url": "https://demo.mesadig.com.br/api/public/orders",
            "data": {"customer_name": "Maria", "customer_phone": "11999990000"},
            "cookies": {"session": "x"},
            "query_string": "k=abc123",
            "headers": {"Authorization": "Bearer token", "asaas-access-token": "segredo", "User-Agent": "iPhone"},
        },
        "user": {"ip_address": "177.1.2.3"},
    }
    clean = _scrub(event, None)
    request = clean["request"]
    assert "data" not in request and "cookies" not in request and "query_string" not in request
    assert request["headers"]["Authorization"] == "[removido]" and request["headers"]["asaas-access-token"] == "[removido]"
    assert request["headers"]["User-Agent"] == "iPhone" and "user" not in clean
