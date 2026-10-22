"""Subscriptions paid online (Asaas): subscribe, change plan, cancel and the payment webhook.

The webhook is the only thing that activates a plan: the browser is never trusted to say "I paid".
"""
import logging
import re
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core import asaas
from app.core.config import settings
from app.core.exceptions import BusinessRuleError
from app.core.plans import PLANS
from app.models.billing_event import BillingEvent
from app.models.tenant import Tenant, TenantStatus
from app.models.user import User
from app.services.audit import record_audit

logger = logging.getLogger(__name__)

PAID_EVENTS = {"PAYMENT_CONFIRMED", "PAYMENT_RECEIVED"}
UNPAID_EVENTS = {"PAYMENT_REFUNDED", "PAYMENT_RECEIVED_IN_CASH_UNDONE", "PAYMENT_CHARGEBACK_REQUESTED", "PAYMENT_REPROVED_BY_RISK_ANALYSIS"}
ENDED_EVENTS = {"SUBSCRIPTION_DELETED", "SUBSCRIPTION_INACTIVATED"}


def _valid_document(digits: str) -> bool:
    def check(base: str, weights: list[int]) -> str:
        total = sum(int(d) * w for d, w in zip(base, weights))
        rest = total % 11
        return "0" if rest < 2 else str(11 - rest)

    if len(digits) == 11 and digits != digits[0] * 11:
        first = (sum(int(d) * w for d, w in zip(digits[:9], range(10, 1, -1))) * 10) % 11 % 10
        second = (sum(int(d) * w for d, w in zip(digits[:10], range(11, 1, -1))) * 10) % 11 % 10
        return digits[9:] == f"{first}{second}"
    if len(digits) == 14 and digits != digits[0] * 14:
        first = check(digits[:12], [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])
        second = check(digits[:12] + first, [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])
        return digits[12:] == first + second
    return False


def billing_blocked(tenant: Tenant, today: date | None = None) -> bool:
    """A paid plan stops taking orders after the grace period of a missed payment, or when a cancelled
    subscription (or a courtesy period not yet paid for) reaches the end of the period it covers."""
    today = today or date.today()
    if tenant.billing_status in ("COURTESY", "PENDING") and tenant.status is TenantStatus.ACTIVE and tenant.paid_until:
        return today > tenant.paid_until
    if tenant.billing_status == "OVERDUE" and tenant.past_due_since:
        return today > tenant.past_due_since + timedelta(days=settings.billing_grace_days)
    if tenant.billing_status == "CANCELED" and tenant.paid_until:
        return today > tenant.paid_until
    return False


def grace_until(tenant: Tenant) -> date | None:
    if tenant.billing_status == "OVERDUE" and tenant.past_due_since:
        return tenant.past_due_since + timedelta(days=settings.billing_grace_days)
    return None


class BillingService:
    def __init__(self, db: Session):
        self.db = db

    # ---- owner actions ------------------------------------------------------------------------
    def subscribe(self, tenant: Tenant, actor: User, plan_key: str, document: str, email: str) -> str | None:
        if not asaas.enabled():
            raise BusinessRuleError("A assinatura online ainda não está disponível. Fale com o suporte.")
        plan = PLANS.get(plan_key)
        if plan is None or plan_key == "trial":
            raise BusinessRuleError("Escolha um plano válido.")
        digits = re.sub(r"\D", "", document)
        if not _valid_document(digits):
            raise BusinessRuleError("Informe um CPF ou CNPJ válido.")
        value = f"{plan.price:.2f}"
        description = f"Mesa Digital · plano {plan.name}"

        if not tenant.billing_customer_id:
            tenant.billing_customer_id = asaas.create_customer(tenant.name, digits, email, tenant.phone, str(tenant.id))
            self.db.commit()
        if tenant.billing_subscription_id and tenant.billing_status in ("PENDING", "ACTIVE", "OVERDUE"):
            asaas.update_subscription(tenant.billing_subscription_id, value, description)
            if tenant.billing_status == "ACTIVE":
                tenant.plan = plan_key  # plan changes apply now; the new price from the next charge
        else:
            # Subscribing during a courtesy period: the first charge only comes when the courtesy ends.
            courtesy_left = tenant.billing_status == "COURTESY" and tenant.paid_until and tenant.paid_until > date.today()
            first_due = tenant.paid_until if courtesy_left else date.today()
            subscription = asaas.create_subscription(
                tenant.billing_customer_id, value, description, str(tenant.id), first_due.isoformat()
            )
            tenant.billing_subscription_id = subscription["id"]
            tenant.billing_status = "PENDING"
        tenant.billing_plan = plan_key
        record_audit(self.db, tenant.id, actor, "BILLING_SUBSCRIBE", "TENANT", tenant.id, f"plano={plan_key}")
        self.db.commit()
        return asaas.pending_payment_url(tenant.billing_subscription_id)

    def payment_url(self, tenant: Tenant) -> str | None:
        if not asaas.enabled() or not tenant.billing_subscription_id:
            return None
        return asaas.pending_payment_url(tenant.billing_subscription_id)

    def cancel(self, tenant: Tenant, actor: User) -> None:
        if not tenant.billing_subscription_id or tenant.billing_status == "CANCELED":
            raise BusinessRuleError("Não há assinatura ativa para cancelar.")
        asaas.delete_subscription(tenant.billing_subscription_id)
        tenant.billing_status = "CANCELED"
        if not tenant.paid_until:
            # Never paid: goes back to the free trial rules (which may already be over).
            tenant.status, tenant.plan = TenantStatus.TRIAL, "trial"
        record_audit(self.db, tenant.id, actor, "BILLING_CANCEL", "TENANT", tenant.id, f"acesso até {tenant.paid_until}")
        self.db.commit()

    # ---- Asaas webhook ------------------------------------------------------------------------
    def handle_webhook(self, payload: dict) -> str:
        event_id, event = str(payload.get("id") or ""), str(payload.get("event") or "")
        if not event_id or not event:
            return "ignored"
        try:
            with self.db.begin_nested():
                self.db.add(BillingEvent(id=event_id[:80], event=event[:60]))
        except IntegrityError:
            return "duplicate"  # Asaas retries; each event applies once

        payment = payload.get("payment") or {}
        subscription_id = payment.get("subscription") or (payload.get("subscription") or {}).get("id")
        tenant = self.db.scalar(select(Tenant).where(Tenant.billing_subscription_id == subscription_id)) if subscription_id else None
        if tenant is None:
            self.db.commit()
            return "unknown subscription"

        due = date.fromisoformat(payment["dueDate"]) if payment.get("dueDate") else date.today()
        if event in PAID_EVENTS:
            month_after = (due.replace(day=1) + timedelta(days=32)).replace(day=min(due.day, 28))
            tenant.paid_until = max(tenant.paid_until or month_after, month_after)
            tenant.billing_status, tenant.past_due_since = "ACTIVE", None
            tenant.status, tenant.plan = TenantStatus.ACTIVE, tenant.billing_plan or tenant.plan
        elif event == "PAYMENT_OVERDUE" and tenant.billing_status != "CANCELED":
            tenant.billing_status = "OVERDUE"
            tenant.past_due_since = tenant.past_due_since or due
        elif event in UNPAID_EVENTS and tenant.billing_status != "CANCELED":
            tenant.billing_status = "OVERDUE"
            tenant.past_due_since = tenant.past_due_since or date.today()
        elif event in ENDED_EVENTS:
            tenant.billing_status = "CANCELED"
        record_audit(self.db, tenant.id, None, "BILLING_WEBHOOK", "TENANT", tenant.id, f"{event} {payment.get('id', '')}")
        self.db.commit()
        logger.info("Billing webhook %s for %s -> %s", event, tenant.slug, tenant.billing_status)
        return "ok"
