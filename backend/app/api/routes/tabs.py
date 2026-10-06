"""Floor staff: open bills per table (comanda), with the alerts that drive the Mesas screen."""
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import staff_only
from app.core.tenancy import get_tenant
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.tab import TabClose, TabReason, TabResponse
from app.services.tab import TabService

router = APIRouter(prefix="/tabs", tags=["Tabs"])


@router.get("", response_model=list[TabResponse])
def list_tabs(tenant: Tenant = Depends(get_tenant), db: Session = Depends(get_db), actor: User = Depends(staff_only)):
    """Every table with an active bill (waiting approval, open or asking for the bill)."""
    service = TabService(db, tenant.id)
    return [service.to_response(tab, tenant) for tab in service.list_active()]


@router.get("/{tab_id}", response_model=TabResponse)
def get_tab(tab_id: UUID, tenant: Tenant = Depends(get_tenant), db: Session = Depends(get_db), actor: User = Depends(staff_only)):
    service = TabService(db, tenant.id)
    return service.to_response(service.get(tab_id), tenant)


@router.post("/{tab_id}/approve", response_model=TabResponse)
def approve_tab(tab_id: UUID, tenant: Tenant = Depends(get_tenant), db: Session = Depends(get_db), actor: User = Depends(staff_only)):
    service = TabService(db, tenant.id)
    return service.to_response(service.approve(tab_id, actor), tenant)


@router.post("/{tab_id}/close", response_model=TabResponse)
def close_tab(
    tab_id: UUID, data: TabClose, tenant: Tenant = Depends(get_tenant), db: Session = Depends(get_db), actor: User = Depends(staff_only),
):
    service = TabService(db, tenant.id)
    return service.to_response(service.close(tab_id, data.payment_method, actor), tenant)


@router.post("/{tab_id}/cancel", response_model=TabResponse)
def cancel_tab(
    tab_id: UUID, data: TabReason, tenant: Tenant = Depends(get_tenant), db: Session = Depends(get_db), actor: User = Depends(staff_only),
):
    service = TabService(db, tenant.id)
    return service.to_response(service.cancel(tab_id, data.reason, actor), tenant)
