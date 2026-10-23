"""Advanced analytics (plan Profissional): who comes back, who is slipping away, when the house is full,
which products carry the revenue and how fast the kitchen works. Everything in the tenant's own time zone."""
from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import and_, case, func, select
from sqlalchemy.orm import Session

from app.models.customer import Customer
from app.models.order import Order, OrderStatus, ServiceType
from app.models.order_item import OrderItem
from app.models.order_status_history import OrderStatusHistory
from app.models.tenant import Tenant
from app.schemas.insights import (
    AbcProduct, ComparisonPoint, CustomerRow, HeatCell, InsightKpis, InsightsResponse, ReasonCount, ServiceTicket,
)
from app.services.analytics import AnalyticsService

# A regular who has not ordered for this long is worth a message; much longer and they are gone.
AT_RISK_FROM_DAYS = 21
AT_RISK_UNTIL_DAYS = 120


def _minutes(value) -> float | None:
    return round(float(value) / 60, 1) if value is not None else None


class InsightsService:
    def __init__(self, db: Session, tenant: Tenant):
        self.db = db
        self.tenant = tenant
        self.analytics = AnalyticsService(db, tenant)

    def build(self, period: str = "month", start: date | None = None, end: date | None = None) -> InsightsResponse:
        conditions, period_start, period_end = self.analytics._filters(period, start, end)
        tenant_id = self.tenant.id
        local = func.timezone(self.tenant.timezone, Order.created_at)
        now = datetime.now(self.analytics.zone)

        revenue, orders = self.db.execute(select(func.coalesce(func.sum(Order.total), 0), func.count(Order.id)).where(*conditions)).one()
        revenue, orders = Decimal(revenue), int(orders)
        items = int(self.db.scalar(select(func.coalesce(func.sum(OrderItem.quantity), 0)).join(Order, Order.id == OrderItem.order_id).where(*conditions)) or 0)

        # Cancellations use every order of the period (the base conditions drop them).
        period_only = [Order.tenant_id == tenant_id]
        if period_start is not None:
            period_only.append(Order.created_at >= period_start)
        if period_end is not None:
            period_only.append(Order.created_at < period_end)
        cancelled = int(self.db.scalar(select(func.count(Order.id)).where(*period_only, Order.status == OrderStatus.CANCELLED)) or 0)
        reasons = self.db.execute(
            select(OrderStatusHistory.reason, func.count())
            .join(Order, Order.id == OrderStatusHistory.order_id)
            .where(*period_only, OrderStatusHistory.status == OrderStatus.CANCELLED)
            .group_by(OrderStatusHistory.reason)
            .order_by(func.count().desc()).limit(6)
        ).all()

        # New vs returning: first order ever (not cancelled) inside the period = new.
        first_order = (
            select(Order.customer_id, func.min(Order.created_at).label("first_at"))
            .where(Order.tenant_id == tenant_id, Order.status != OrderStatus.CANCELLED)
            .group_by(Order.customer_id).subquery()
        )
        in_period = (
            select(Order.customer_id, func.count(Order.id).label("n")).where(*conditions).group_by(Order.customer_id).subquery()
        )
        is_new = first_order.c.first_at >= period_start if period_start is not None else in_period.c.n == 1
        customers, new_customers = self.db.execute(
            select(func.count(), func.coalesce(func.sum(case((and_(is_new, in_period.c.n == 1), 1), else_=0)), 0)).select_from(in_period).join(first_order, first_order.c.customer_id == in_period.c.customer_id)
        ).one()
        customers, new_customers = int(customers), int(new_customers)
        returning = customers - new_customers  # includes new customers who already came back within the period

        # Kitchen speed: received -> ready, and received -> delivered for deliveries.
        ready_at = (
            select(OrderStatusHistory.order_id, func.min(OrderStatusHistory.created_at).label("at"))
            .where(OrderStatusHistory.status == OrderStatus.READY).group_by(OrderStatusHistory.order_id).subquery()
        )
        finished_at = (
            select(OrderStatusHistory.order_id, func.min(OrderStatusHistory.created_at).label("at"))
            .where(OrderStatusHistory.status == OrderStatus.FINISHED).group_by(OrderStatusHistory.order_id).subquery()
        )
        prep = self.db.scalar(
            select(func.avg(func.extract("epoch", ready_at.c.at - Order.created_at)))
            .join(ready_at, ready_at.c.order_id == Order.id).where(*conditions, ready_at.c.at > Order.created_at)
        )
        delivery = self.db.scalar(
            select(func.avg(func.extract("epoch", finished_at.c.at - Order.created_at)))
            .join(finished_at, finished_at.c.order_id == Order.id)
            .where(*conditions, Order.service_type == ServiceType.DELIVERY, finished_at.c.at > Order.created_at)
        )

        coupon_orders, coupon_revenue, discount_total = self.db.execute(
            select(func.count(Order.id), func.coalesce(func.sum(Order.total), 0), func.coalesce(func.sum(Order.discount), 0))
            .where(*conditions, Order.coupon_code.is_not(None))
        ).one()

        # Month-end projection: only meaningful for the month in progress.
        projected = None
        if period == "month" and start is None and period_start is not None and period_start.month == now.month and period_start.year == now.year:
            elapsed = (now - period_start).total_seconds() / 86400
            days_in_month = calendar.monthrange(now.year, now.month)[1]
            if elapsed >= 1:
                projected = (revenue / Decimal(str(elapsed)) * days_in_month).quantize(Decimal("0.01"))

        heat_rows = self.db.execute(
            select(func.extract("isodow", local).label("dow"), func.extract("hour", local).label("hour"),
                   func.count(Order.id), func.coalesce(func.sum(Order.total), 0))
            .where(*conditions).group_by("dow", "hour")
        ).all()

        comparison = self._comparison(conditions, period_start, period_end, now)

        dashboard = self.analytics.dashboard(period, start, end, product_limit=None)
        by_revenue = sorted(dashboard.products, key=lambda p: -p.revenue)
        abc, running = [], Decimal(0)
        for product in by_revenue:
            share = float(product.revenue / revenue) if revenue else 0.0
            before = float(running / revenue) if revenue else 0.0
            running += product.revenue
            abc.append(AbcProduct(product_name=product.product_name, quantity=product.quantity, revenue=product.revenue, share=share,
                                  cumulative=float(running / revenue) if revenue else 0.0, grade="A" if before < 0.8 else "B" if before < 0.95 else "C"))

        tickets = self.db.execute(
            select(Order.service_type, func.count(Order.id), func.avg(Order.total), func.sum(Order.total))
            .where(*conditions).group_by(Order.service_type).order_by(func.count(Order.id).desc())
        ).all()

        top = self._customers(
            select(Customer.id, Customer.name, Customer.phone, func.count(Order.id), func.sum(Order.total), func.max(Order.created_at))
            .join(Order, Order.customer_id == Customer.id).where(*conditions)
            .group_by(Customer.id).order_by(func.sum(Order.total).desc()).limit(10), now)
        at_risk = self._customers(
            select(Customer.id, Customer.name, Customer.phone, func.count(Order.id), func.sum(Order.total), func.max(Order.created_at))
            .join(Order, Order.customer_id == Customer.id)
            .where(Order.tenant_id == tenant_id, Order.status != OrderStatus.CANCELLED, Customer.active.is_(True),
                   Customer.marketing_opt_in.is_(True))  # LGPD: promotions only with consent
            .group_by(Customer.id)
            .having(func.count(Order.id) >= 2,
                    func.max(Order.created_at) < now - timedelta(days=AT_RISK_FROM_DAYS),
                    func.max(Order.created_at) >= now - timedelta(days=AT_RISK_UNTIL_DAYS))
            .order_by(func.sum(Order.total).desc()).limit(30), now)
        lapsed_without_consent = int(self.db.scalar(
            select(func.count()).select_from(
                select(Customer.id).join(Order, Order.customer_id == Customer.id)
                .where(Order.tenant_id == tenant_id, Order.status != OrderStatus.CANCELLED, Customer.active.is_(True),
                       Customer.marketing_opt_in.is_(False))
                .group_by(Customer.id)
                .having(func.count(Order.id) >= 2,
                        func.max(Order.created_at) < now - timedelta(days=AT_RISK_FROM_DAYS),
                        func.max(Order.created_at) >= now - timedelta(days=AT_RISK_UNTIL_DAYS)).subquery()
            )
        ) or 0)

        return InsightsResponse(
            period_start=period_start.isoformat() if period_start else "",
            period_end=period_end.isoformat() if period_end else "",
            kpis=InsightKpis(
                customers=customers, new_customers=new_customers, returning_customers=returning,
                returning_rate=returning / customers if customers else 0.0,
                items_per_order=round(items / orders, 2) if orders else 0.0,
                cancellation_rate=cancelled / (orders + cancelled) if orders + cancelled else 0.0, cancelled_orders=cancelled,
                avg_prep_minutes=_minutes(prep), avg_delivery_minutes=_minutes(delivery),
                coupon_orders=int(coupon_orders), coupon_revenue=Decimal(coupon_revenue), discount_total=Decimal(discount_total),
                projected_revenue=projected, revenue_so_far=revenue,
            ),
            heatmap=[HeatCell(weekday=int(r[0]) - 1, hour=int(r[1]), orders=int(r[2]), revenue=Decimal(r[3])) for r in heat_rows],
            comparison=comparison,
            abc=abc,
            tickets_by_service=[ServiceTicket(service_type=r[0].value, orders=int(r[1]), average_ticket=Decimal(r[2]).quantize(Decimal("0.01")),
                                              revenue=Decimal(r[3])) for r in tickets],
            top_customers=top,
            at_risk=at_risk,
            lapsed_without_consent=lapsed_without_consent,
            cancellation_reasons=[ReasonCount(reason=r[0] or "Sem motivo informado", count=int(r[1])) for r in reasons],
        )

    def _customers(self, statement, now: datetime) -> list[CustomerRow]:
        return [
            CustomerRow(customer_id=str(r[0]), name=r[1], phone=r[2], orders=int(r[3]), total_spent=Decimal(r[4]),
                        last_order_at=r[5], days_since=max(0, (now - r[5]).days))
            for r in self.db.execute(statement).all()
        ]

    def _comparison(self, conditions, period_start, period_end, now) -> list[ComparisonPoint]:
        """Cumulative revenue day by day, against the same number of days right before the period."""
        if period_start is None or period_end is None:
            return []
        local_day = func.date(func.timezone(self.tenant.timezone, Order.created_at))
        length = (period_end - period_start).days
        previous_start = period_start - (period_end - period_start)

        def daily(start, end):
            rows = self.db.execute(
                select(local_day, func.sum(Order.total))
                .where(Order.tenant_id == self.tenant.id, Order.status != OrderStatus.CANCELLED,
                       Order.created_at >= start, Order.created_at < end)
                .group_by(local_day)
            ).all()
            return {row[0]: Decimal(row[1]) for row in rows}

        current, previous = daily(period_start, period_end), daily(previous_start, period_start)
        has_previous = bool(previous)
        points, running_current, running_previous = [], Decimal(0), Decimal(0)
        last_day = min(length, max(1, (now.date() - period_start.date()).days + 1))
        for index in range(length):
            running_current += current.get(period_start.date() + timedelta(days=index), Decimal(0))
            running_previous += previous.get(previous_start.date() + timedelta(days=index), Decimal(0))
            points.append(ComparisonPoint(day=index + 1, current=running_current if index < last_day else None,
                                          previous=running_previous if has_previous else None))
        return points
