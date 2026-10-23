"""Fechamento de caixa: what came in on one day, by payment method, and what is still open."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.labels import PAYMENT_LABELS
from app.models.order import Order, OrderStatus, PaymentStatus
from app.models.tab import ACTIVE_TAB_STATUSES, Tab
from app.models.tab_payment import TabPayment, TabPaymentStatus
from app.models.tenant import Tenant


class MethodTotal(BaseModel):
    method: str
    label: str
    count: int
    amount: Decimal


class CashReport(BaseModel):
    day: date
    received: list[MethodTotal]
    received_total: Decimal
    orders: int
    cancelled: int
    cancelled_amount: Decimal
    discounts: Decimal
    service_fees: Decimal
    delivery_fees: Decimal
    pending_orders: int  # created that day, not paid yet (outside table bills)
    pending_amount: Decimal
    open_tabs: int
    pix_to_confirm: int  # PIX the customers reported, not checked yet


def cash_report(db: Session, tenant: Tenant, day: date) -> CashReport:
    zone = ZoneInfo(tenant.timezone)
    start = datetime.combine(day, time.min, tzinfo=zone)
    end = start + timedelta(days=1)
    totals: dict[str, list] = {}

    # Orders paid on their own (counter, delivery, PIX order), by the moment the money came in.
    for method, count, amount in db.execute(
        select(Order.payment_method, func.count(Order.id), func.sum(Order.total))
        .where(Order.tenant_id == tenant.id, Order.tab_id.is_(None), Order.payment_status == PaymentStatus.PAID,
               Order.status != OrderStatus.CANCELLED, Order.paid_at >= start, Order.paid_at < end)
        .group_by(Order.payment_method)
    ):
        totals.setdefault(method.value, [0, Decimal(0)])
        totals[method.value][0] += count
        totals[method.value][1] += Decimal(amount)
    # Table bills: every confirmed payment (whole bill or one person's share).
    for method, count, amount in db.execute(
        select(TabPayment.method, func.count(TabPayment.id), func.sum(TabPayment.amount))
        .where(TabPayment.tenant_id == tenant.id, TabPayment.status == TabPaymentStatus.CONFIRMED,
               func.coalesce(TabPayment.resolved_at, TabPayment.created_at) >= start,
               func.coalesce(TabPayment.resolved_at, TabPayment.created_at) < end)
        .group_by(TabPayment.method)
    ):
        totals.setdefault(method.value, [0, Decimal(0)])
        totals[method.value][0] += count
        totals[method.value][1] += Decimal(amount)

    created = [Order.tenant_id == tenant.id, Order.created_at >= start, Order.created_at < end]
    orders, discounts, service_fees, delivery_fees = db.execute(
        select(func.count(Order.id), func.coalesce(func.sum(Order.discount), 0), func.coalesce(func.sum(Order.service_fee), 0),
               func.coalesce(func.sum(Order.delivery_fee), 0)).where(*created, Order.status != OrderStatus.CANCELLED)
    ).one()
    cancelled, cancelled_amount = db.execute(
        select(func.count(Order.id), func.coalesce(func.sum(Order.total), 0)).where(*created, Order.status == OrderStatus.CANCELLED)
    ).one()
    pending, pending_amount = db.execute(
        select(func.count(Order.id), func.coalesce(func.sum(Order.total), 0))
        .where(*created, Order.status != OrderStatus.CANCELLED, Order.payment_status != PaymentStatus.PAID, Order.tab_id.is_(None))
    ).one()
    open_tabs = db.scalar(select(func.count(Tab.id)).where(Tab.tenant_id == tenant.id, Tab.status.in_(ACTIVE_TAB_STATUSES))) or 0
    pix_to_confirm = db.scalar(select(func.count(TabPayment.id)).where(TabPayment.tenant_id == tenant.id, TabPayment.status == TabPaymentStatus.REPORTED)) or 0

    received = sorted(
        (MethodTotal(method=m, label=PAYMENT_LABELS.get(m, m), count=c, amount=a) for m, (c, a) in totals.items()),
        key=lambda item: -item.amount,
    )
    return CashReport(
        day=day, received=received, received_total=sum((r.amount for r in received), Decimal(0)), orders=int(orders),
        cancelled=int(cancelled), cancelled_amount=Decimal(cancelled_amount), discounts=Decimal(discounts),
        service_fees=Decimal(service_fees), delivery_fees=Decimal(delivery_fees), pending_orders=int(pending),
        pending_amount=Decimal(pending_amount), open_tabs=int(open_tabs), pix_to_confirm=int(pix_to_confirm),
    )
