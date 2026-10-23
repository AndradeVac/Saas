from datetime import date

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.plans import EXPORTS, require_feature
from app.core.security import admin_only
from app.core.tenancy import get_tenant
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.analytics import DashboardAnalyticsResponse
from app.services.analytics import AnalyticsService
from app.services.reports import XLSX_TYPE, build_sales_report, sales_report_pdf, sales_report_xlsx

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/dashboard", response_model=DashboardAnalyticsResponse)
def get_dashboard_analytics(
    period: str = Query(default="month", pattern="^(month|quarter|all)$"),
    start: date | None = Query(default=None),
    end: date | None = Query(default=None),
    tenant: Tenant = Depends(get_tenant),
    db: Session = Depends(get_db),
    _: User = Depends(admin_only),
):
    return AnalyticsService(db, tenant).dashboard(period, start, end)


@router.get("/dashboard/export", dependencies=[Depends(require_feature(EXPORTS))])
def export_dashboard(
    period: str = Query(default="month", pattern="^(month|quarter|all)$"),
    start: date | None = Query(default=None),
    end: date | None = Query(default=None),
    file_format: str = Query(default="xlsx", alias="format", pattern="^(xlsx|pdf)$"),
    tenant: Tenant = Depends(get_tenant),
    db: Session = Depends(get_db),
    _: User = Depends(admin_only),
):
    report = build_sales_report(db, tenant, period, start, end)
    name = f"{tenant.slug}-relatorio-de-vendas-{report.generated_at:%Y-%m-%d}"
    if file_format == "pdf":
        return Response(content=sales_report_pdf(report), media_type="application/pdf",
                        headers={"Content-Disposition": f"attachment; filename={name}.pdf"})
    return Response(content=sales_report_xlsx(report), media_type=XLSX_TYPE,
                    headers={"Content-Disposition": f"attachment; filename={name}.xlsx"})
