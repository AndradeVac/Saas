"""Registers (or updates) the Asaas webhook that activates subscriptions automatically.

Usage (from backend/, with ASAAS_API_KEY and ASAAS_WEBHOOK_TOKEN set to the production values):
    python -m scripts.asaas_webhook https://mesadig.com.br/api/billing/webhook
"""
import sys

from app.core import asaas
from app.core.config import settings

EVENTS = [
    "PAYMENT_CONFIRMED", "PAYMENT_RECEIVED", "PAYMENT_OVERDUE", "PAYMENT_REFUNDED", "PAYMENT_RECEIVED_IN_CASH_UNDONE",
    "PAYMENT_CHARGEBACK_REQUESTED", "PAYMENT_REPROVED_BY_RISK_ANALYSIS", "SUBSCRIPTION_DELETED", "SUBSCRIPTION_INACTIVATED",
]
NAME = "Mesa Digital - assinaturas"


def main() -> int:
    if len(sys.argv) != 2 or not settings.asaas_api_key or len(settings.asaas_webhook_token) < 32:
        sys.exit(__doc__)
    # Failure notices go to the e-mail already registered on the Asaas account.
    email = asaas._request("GET", "/myAccount").get("email")
    body = {
        "name": NAME, "url": sys.argv[1], "email": email, "enabled": True, "interrupted": False, "apiVersion": 3,
        "authToken": settings.asaas_webhook_token, "sendType": "SEQUENTIALLY", "events": EVENTS,
    }
    existing = next((w for w in asaas._request("GET", "/webhooks").get("data", []) if w.get("name") == NAME), None)
    result = asaas._request("PUT", f"/webhooks/{existing['id']}", body) if existing else asaas._request("POST", "/webhooks", body)
    print(f"Webhook {'atualizado' if existing else 'criado'}: {result.get('id')} -> {result.get('url')} (ativo: {result.get('enabled')})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
