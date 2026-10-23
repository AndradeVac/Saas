from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class InsightKpis(BaseModel):
    customers: int
    new_customers: int
    returning_customers: int
    returning_rate: float  # 0..1 of the period's customers who had bought before (or came back in the period)
    items_per_order: float
    cancellation_rate: float
    cancelled_orders: int
    avg_prep_minutes: float | None  # received -> ready
    avg_delivery_minutes: float | None  # received -> delivered, delivery orders only
    coupon_orders: int
    coupon_revenue: Decimal
    discount_total: Decimal
    projected_revenue: Decimal | None  # month-to-date pace extended to the whole month (current month only)
    revenue_so_far: Decimal


class HeatCell(BaseModel):
    weekday: int  # 0 = Monday
    hour: int
    orders: int
    revenue: Decimal


class ComparisonPoint(BaseModel):
    day: int  # 1-based day of the period
    current: Decimal | None  # cumulative revenue (None for days still to come)
    previous: Decimal | None


class AbcProduct(BaseModel):
    product_name: str
    quantity: int
    revenue: Decimal
    share: float
    cumulative: float
    grade: str  # A: first 80% of revenue, B: next 15%, C: the rest


class ServiceTicket(BaseModel):
    service_type: str
    orders: int
    average_ticket: Decimal
    revenue: Decimal


class CustomerRow(BaseModel):
    customer_id: str
    name: str
    phone: str | None
    orders: int
    total_spent: Decimal
    last_order_at: datetime
    days_since: int


class ReasonCount(BaseModel):
    reason: str
    count: int


class InsightsResponse(BaseModel):
    period_start: str
    period_end: str
    kpis: InsightKpis
    heatmap: list[HeatCell]
    comparison: list[ComparisonPoint]
    abc: list[AbcProduct]
    tickets_by_service: list[ServiceTicket]
    top_customers: list[CustomerRow]
    at_risk: list[CustomerRow]
    cancellation_reasons: list[ReasonCount]
