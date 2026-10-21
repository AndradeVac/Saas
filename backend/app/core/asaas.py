"""Minimal Asaas API client (https://docs.asaas.com), only what subscriptions need."""
import json
import logging
import urllib.error
import urllib.request

from app.core.config import settings
from app.core.exceptions import BusinessRuleError

logger = logging.getLogger(__name__)


class AsaasError(BusinessRuleError):
    pass


def enabled() -> bool:
    return bool(settings.asaas_api_key)


def _request(method: str, path: str, body: dict | None = None) -> dict:
    request = urllib.request.Request(
        f"{settings.asaas_base_url.rstrip('/')}{path}",
        data=json.dumps(body).encode() if body is not None else None,
        headers={"access_token": settings.asaas_api_key, "Content-Type": "application/json", "User-Agent": "mesa-digital"},
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:  # noqa: S310 - fixed https host
            return json.loads(response.read() or b"{}")
    except urllib.error.HTTPError as error:
        try:
            errors = json.loads(error.read()).get("errors") or []
            message = errors[0].get("description") if errors else ""
        except Exception:
            message = ""
        logger.warning("Asaas %s %s failed: %s %s", method, path, error.code, message)
        raise AsaasError(message or "Não foi possível falar com o sistema de pagamentos agora. Tente novamente.") from error
    except urllib.error.URLError as error:
        logger.warning("Asaas unreachable: %s", error)
        raise AsaasError("Não foi possível falar com o sistema de pagamentos agora. Tente novamente.") from error


def create_customer(name: str, document: str, email: str, phone: str | None, reference: str) -> str:
    body = {"name": name, "cpfCnpj": document, "email": email, "externalReference": reference, "notificationDisabled": False}
    if phone:
        body["mobilePhone"] = phone
    return _request("POST", "/customers", body)["id"]


def create_subscription(customer_id: str, value: str, description: str, reference: str, next_due_date: str) -> dict:
    return _request("POST", "/subscriptions", {
        "customer": customer_id,
        "billingType": "UNDEFINED",  # the customer picks PIX, boleto or card on Asaas' page
        "value": value,
        "nextDueDate": next_due_date,
        "cycle": "MONTHLY",
        "description": description,
        "externalReference": reference,
    })


def update_subscription(subscription_id: str, value: str, description: str) -> dict:
    return _request("POST", f"/subscriptions/{subscription_id}", {
        "value": value, "description": description, "updatePendingPayments": True,
    })


def delete_subscription(subscription_id: str) -> None:
    _request("DELETE", f"/subscriptions/{subscription_id}")


def pending_payment_url(subscription_id: str) -> str | None:
    """Payment page (invoice) of the oldest open charge of the subscription, if any."""
    data = _request("GET", f"/subscriptions/{subscription_id}/payments?status=PENDING&limit=10")
    payments = sorted(data.get("data") or [], key=lambda p: p.get("dueDate", ""))
    if not payments:
        data = _request("GET", f"/subscriptions/{subscription_id}/payments?status=OVERDUE&limit=10")
        payments = sorted(data.get("data") or [], key=lambda p: p.get("dueDate", ""))
    return payments[0].get("invoiceUrl") if payments else None
