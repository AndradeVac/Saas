from datetime import date, datetime, time, timedelta
from decimal import Decimal
from io import BytesIO
from zoneinfo import ZoneInfo

from openpyxl import Workbook
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessRuleError
from app.models.category import Category
from app.models.order import Order, OrderStatus
from app.models.order_item import OrderItem
from app.models.product import Product
from app.models.tenant import Tenant
from app.schemas.analytics import (
    BreakdownSummary,
    CategorySalesSummary,
    DashboardAnalyticsResponse,
    DaySalesSummary,
    HourSalesSummary,
    ProductSalesSummary,
)

# Cancelled orders never became sales.
_EXCLUDED_STATUSES = (OrderStatus.CANCELLED,)
_PERIODS = {"month", "quarter", "all"}


class AnalyticsService:
    """Dashboard numbers for one tenant. Periods and hours follow the tenant's own time zone."""

    def __init__(self, db: Session, tenant: Tenant):
        self.db = db
        self.tenant = tenant
        self.zone = ZoneInfo(tenant.timezone)

    def period_bounds(self, period: str) -> tuple[datetime | None, datetime | None]:
        if period == "all":
            return None, None
        today = datetime.now(self.zone)
        months = 3 if period == "quarter" else 1
        first_month = ((today.month - 1) // 3) * 3 + 1 if period == "quarter" else today.month
        start = datetime(today.year, first_month, 1, tzinfo=self.zone)
        total_months = start.month - 1 + months
        end = datetime(start.year + total_months // 12, total_months % 12 + 1, 1, tzinfo=self.zone)
        return start, end

    def _custom_bounds(self, start: date, end: date) -> tuple[datetime, datetime]:
        if end < start:
            raise BusinessRuleError("A data final deve ser igual ou posterior à data inicial.")
        return (
            datetime.combine(start, time.min, tzinfo=self.zone),
            datetime.combine(end + timedelta(days=1), time.min, tzinfo=self.zone),
        )

    def _filters(self, period: str, start: date | None, end: date | None):
        if start is not None and end is not None:
            period_start, period_end = self._custom_bounds(start, end)
        else:
            period_start, period_end = self.period_bounds(period)
        conditions = [Order.tenant_id == self.tenant.id, Order.status.not_in(_EXCLUDED_STATUSES)]
        if period_start is not None:
            conditions.append(Order.created_at >= period_start)
        if period_end is not None:
            conditions.append(Order.created_at < period_end)
        return conditions, period_start, period_end

    def dashboard(
        self,
        period: str = "month",
        custom_start: date | None = None,
        custom_end: date | None = None,
    ) -> DashboardAnalyticsResponse:
        if period not in _PERIODS:
            raise BusinessRuleError("Período inválido. Use month, quarter ou all.")

        conditions, start, end = self._filters(period, custom_start, custom_end)
        local_created_at = func.timezone(self.tenant.timezone, Order.created_at)

        revenue, order_count, average_ticket = self.db.execute(
            select(
                func.coalesce(func.sum(Order.total), 0),
                func.count(Order.id),
                func.coalesce(func.avg(Order.total), 0),
            ).where(*conditions)
        ).one()

        product_rows = self.db.execute(
            select(
                OrderItem.product_id,
                Product.name.label("product_name"),
                func.sum(OrderItem.quantity).label("quantity"),
                func.sum(OrderItem.total_price).label("revenue"),
            )
            .join(Order, Order.id == OrderItem.order_id)
            .join(Product, Product.id == OrderItem.product_id)
            .where(*conditions)
            .group_by(OrderItem.product_id, Product.name)
            .order_by(func.sum(OrderItem.quantity).desc())
            .limit(10)
        ).all()

        category_rows = self.db.execute(
            select(
                Category.name.label("category_name"),
                func.sum(OrderItem.quantity).label("quantity"),
                func.sum(OrderItem.total_price).label("revenue"),
            )
            .join(Order, Order.id == OrderItem.order_id)
            .join(Product, Product.id == OrderItem.product_id)
            .join(Category, Category.id == Product.category_id)
            .where(*conditions)
            .group_by(Category.name)
            .order_by(func.sum(OrderItem.total_price).desc())
        ).all()

        hourly_rows = self.db.execute(
            select(
                func.extract("hour", local_created_at).label("hour"),
                func.count(Order.id).label("orders"),
                func.sum(Order.total).label("revenue"),
            )
            .where(*conditions)
            .group_by(func.extract("hour", local_created_at))
            .order_by(func.extract("hour", local_created_at))
        ).all()

        day = func.date(local_created_at)
        daily_rows = self.db.execute(
            select(day.label("day"), func.count(Order.id).label("orders"), func.sum(Order.total).label("revenue"))
            .where(*conditions)
            .group_by(day)
            .order_by(day)
        ).all()

        def breakdown(column):
            rows = self.db.execute(
                select(column, func.count(Order.id)).where(*conditions).group_by(column).order_by(column)
            ).all()
            return [BreakdownSummary(label=row[0].value, count=int(row[1])) for row in rows]

        previous_revenue = Decimal("0")
        revenue_change_percent = Decimal("0")
        if start is not None and end is not None:
            previous_start = start - (end - start)
            previous_revenue = Decimal(self.db.scalar(
                select(func.coalesce(func.sum(Order.total), 0)).where(
                    Order.tenant_id == self.tenant.id,
                    Order.status.not_in(_EXCLUDED_STATUSES),
                    Order.created_at >= previous_start,
                    Order.created_at < start,
                )
            ) or 0)
            if previous_revenue:
                revenue_change_percent = ((Decimal(revenue) - previous_revenue) / previous_revenue * 100).quantize(Decimal("0.01"))

        products = [
            ProductSalesSummary(product_name=row.product_name, quantity=int(row.quantity), revenue=Decimal(row.revenue))
            for row in product_rows
        ]
        return DashboardAnalyticsResponse(
            period=period if custom_start is None or custom_end is None else "custom",
            period_start=start.isoformat() if start else "",
            period_end=end.isoformat() if end else "",
            revenue=Decimal(revenue),
            order_count=int(order_count),
            average_ticket=Decimal(average_ticket).quantize(Decimal("0.01")),
            top_product=products[0] if products else None,
            products=products,
            categories=[
                CategorySalesSummary(category_name=row.category_name, quantity=int(row.quantity), revenue=Decimal(row.revenue))
                for row in category_rows
            ],
            sales_by_hour=[
                HourSalesSummary(hour=int(row.hour), orders=int(row.orders), revenue=Decimal(row.revenue))
                for row in hourly_rows
            ],
            sales_by_day=[
                DaySalesSummary(day=row.day.isoformat(), orders=int(row.orders), revenue=Decimal(row.revenue))
                for row in daily_rows
            ],
            orders_by_status=breakdown(Order.status),
            orders_by_payment=breakdown(Order.payment_method),
            orders_by_service=breakdown(Order.service_type),
            previous_revenue=previous_revenue,
            revenue_change_percent=revenue_change_percent,
        )

    def export_xlsx(self, period: str) -> bytes:
        dashboard = self.dashboard(period)
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Resumo"
        sheet.append([self.tenant.name])
        sheet.append(["Período", dashboard.period])
        sheet.append(["Faturamento", float(dashboard.revenue)])
        sheet.append(["Pedidos", dashboard.order_count])
        sheet.append(["Ticket médio", float(dashboard.average_ticket)])
        sheet.append([])
        sheet.append(["Produto", "Quantidade", "Receita"])
        for product in dashboard.products:
            sheet.append([product.product_name, product.quantity, float(product.revenue)])
        output = BytesIO()
        workbook.save(output)
        return output.getvalue()

    def export_pdf(self, period: str) -> bytes:
        dashboard = self.dashboard(period)
        output = BytesIO()
        document = canvas.Canvas(output, pagesize=A4)
        document.setTitle(f"{self.tenant.name} - Dashboard")
        document.setFont("Helvetica-Bold", 18)
        document.drawString(48, 790, f"{self.tenant.name} - Dashboard")
        document.setFont("Helvetica", 10)
        document.drawString(48, 770, f"Período: {dashboard.period}")
        document.drawString(48, 750, f"Faturamento: R$ {dashboard.revenue:.2f}")
        document.drawString(48, 732, f"Pedidos: {dashboard.order_count}")
        document.drawString(48, 714, f"Ticket médio: R$ {dashboard.average_ticket:.2f}")
        document.setFont("Helvetica-Bold", 12)
        document.drawString(48, 680, "Produtos mais vendidos")
        document.setFont("Helvetica", 10)
        y_position = 660
        for index, product in enumerate(dashboard.products[:10], start=1):
            document.drawString(58, y_position, f"{index}. {product.product_name} - {product.quantity} un. - R$ {product.revenue:.2f}")
            y_position -= 18
        document.save()
        return output.getvalue()
