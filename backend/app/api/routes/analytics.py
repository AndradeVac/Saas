from datetime import date

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import admin_only
from app.core.tenancy import get_tenant
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.analytics import DashboardAnalyticsResponse
from app.services.analytics import AnalyticsService

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


@router.get("/dashboard/export")
def export_dashboard(
    period: str = Query(default="month", pattern="^(month|quarter|all)$"),
    file_format: str = Query(default="xlsx", alias="format", pattern="^(xlsx|pdf)$"),
    tenant: Tenant = Depends(get_tenant),
    db: Session = Depends(get_db),
    _: User = Depends(admin_only),
):
    service = AnalyticsService(db, tenant)
    if file_format == "pdf":
        return Response(
            content=service.export_pdf(period),
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={tenant.slug}-dashboard-{period}.pdf"},
        )
    return Response(
        content=service.export_xlsx(period),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={tenant.slug}-dashboard-{period}.xlsx"},
    )
