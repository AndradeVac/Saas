from decimal import Decimal

from pydantic import BaseModel


class ProductSalesSummary(BaseModel):
    product_name: str
    quantity: int
    revenue: Decimal


class CategorySalesSummary(BaseModel):
    category_name: str
    quantity: int
    revenue: Decimal


class HourSalesSummary(BaseModel):
    hour: int
    orders: int
    revenue: Decimal


class DaySalesSummary(BaseModel):
    day: str
    orders: int
    revenue: Decimal


class BreakdownSummary(BaseModel):
    label: str
    count: int


class DashboardAnalyticsResponse(BaseModel):
    period: str
    period_start: str
    period_end: str
    revenue: Decimal
    order_count: int
    average_ticket: Decimal
    top_product: ProductSalesSummary | None
    products: list[ProductSalesSummary]
    categories: list[CategorySalesSummary]
    sales_by_hour: list[HourSalesSummary]
    sales_by_day: list[DaySalesSummary]
    orders_by_status: list[BreakdownSummary]
    orders_by_payment: list[BreakdownSummary]
    orders_by_service: list[BreakdownSummary]
    previous_revenue: Decimal = Decimal("0")
    revenue_change_percent: Decimal = Decimal("0")
