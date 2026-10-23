from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import admin_only
from app.core.tenancy import get_tenant
from app.models.tenant import Tenant
from app.models.user import User
from app.services import marketing

router = APIRouter(prefix="/marketing", tags=["Marketing"])


@router.get("/table-cards.pdf")
def table_cards(
    labels: list[str] = Query(min_length=1, max_length=200), tenant: Tenant = Depends(get_tenant),
    db: Session = Depends(get_db), _: User = Depends(admin_only),
):
    return Response(marketing.table_cards_pdf(db, tenant, labels), media_type="application/pdf",
                    headers={"Content-Disposition": f"attachment; filename={tenant.slug}-qr-mesas.pdf"})


@router.get("/poster.pdf")
def poster(tenant: Tenant = Depends(get_tenant), db: Session = Depends(get_db), _: User = Depends(admin_only)):
    return Response(marketing.poster_pdf(db, tenant), media_type="application/pdf",
                    headers={"Content-Disposition": f"attachment; filename={tenant.slug}-cartaz.pdf"})


@router.get("/instagram.png")
def instagram(tenant: Tenant = Depends(get_tenant), db: Session = Depends(get_db), _: User = Depends(admin_only)):
    return Response(marketing.instagram_png(db, tenant), media_type="image/png",
                    headers={"Content-Disposition": f"attachment; filename={tenant.slug}-post-instagram.png"})
