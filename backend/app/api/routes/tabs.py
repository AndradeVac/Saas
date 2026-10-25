"""Floor staff: open bills per table (comanda), with the alerts that drive the Mesas screen."""
from uuid import UUID

from urllib.parse import quote

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.config import settings
from app.core.security import admin_only, staff_only
from app.core.tables import normalize_table_label, table_code
from app.core.tenancy import get_tenant
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.tab import ServiceFeeChoice, TableQr, TabClose, TabPaymentCreate, TabReason, TabResponse
from app.services.tab import TabService

router = APIRouter(prefix="/tabs", tags=["Tabs"])


@router.get("", response_model=list[TabResponse])
def list_tabs(tenant: Tenant = Depends(get_tenant), db: Session = Depends(get_db), actor: User = Depends(staff_only)):
    """Every table with an active bill (waiting approval, open or asking for the bill)."""
    service = TabService(db, tenant.id)
    return [service.to_response(tab, tenant) for tab in service.list_active()]


@router.get("/qr-codes", response_model=list[TableQr])
def table_qr_codes(
    labels: list[str] = Query(min_length=1, max_length=200),
    tenant: Tenant = Depends(get_tenant),
    _: User = Depends(admin_only),
):
    """Menu link for each table, with the secret code the comanda requires. Used to print the QR Codes."""
    result = []
    for raw in labels:
        label = normalize_table_label(raw)
        if label:
            code = table_code(tenant.table_secret, label)
            result.append(TableQr(label=label, code=code, url=settings.tenant_url(tenant.slug, f"/?mesa={quote(label)}&k={code}")))
    return result


@router.get("/{tab_id}", response_model=TabResponse)
def get_tab(tab_id: UUID, tenant: Tenant = Depends(get_tenant), db: Session = Depends(get_db), actor: User = Depends(staff_only)):
    service = TabService(db, tenant.id)
    return service.to_response(service.get(tab_id), tenant)


@router.post("/{tab_id}/approve", response_model=TabResponse)
def approve_tab(tab_id: UUID, tenant: Tenant = Depends(get_tenant), db: Session = Depends(get_db), actor: User = Depends(staff_only)):
    service = TabService(db, tenant.id)
    return service.to_response(service.approve(tab_id, actor), tenant)


@router.post("/{tab_id}/call/answer", response_model=TabResponse)
def answer_waiter_call(tab_id: UUID, tenant: Tenant = Depends(get_tenant), db: Session = Depends(get_db), _: User = Depends(staff_only)):
    service = TabService(db, tenant.id)
    return service.to_response(service.answer_call(service.get(tab_id)), tenant)


@router.post("/{tab_id}/service-fee", response_model=TabResponse)
def tab_service_fee(
    tab_id: UUID, data: ServiceFeeChoice, tenant: Tenant = Depends(get_tenant), db: Session = Depends(get_db), _: User = Depends(staff_only),
):
    service = TabService(db, tenant.id)
    return service.to_response(service.set_service_fee(service.get(tab_id), tenant, data.waived), tenant)


@router.post("/{tab_id}/close", response_model=TabResponse)
def close_tab(
    tab_id: UUID, data: TabClose, tenant: Tenant = Depends(get_tenant), db: Session = Depends(get_db), actor: User = Depends(staff_only),
):
    service = TabService(db, tenant.id)
    return service.to_response(service.close(tab_id, data.payment_method, actor), tenant)


@router.post("/{tab_id}/payments", response_model=TabResponse)
def add_tab_payment(
    tab_id: UUID, data: TabPaymentCreate, tenant: Tenant = Depends(get_tenant), db: Session = Depends(get_db), actor: User = Depends(staff_only),
):
    """One person's share received (cash, card or PIX checked in the bank)."""
    service = TabService(db, tenant.id)
    return service.to_response(service.add_payment(tab_id, data.amount, data.payment_method, actor), tenant)


@router.post("/{tab_id}/payments/{payment_id}/confirm", response_model=TabResponse)
def confirm_tab_payment(
    tab_id: UUID, payment_id: UUID, tenant: Tenant = Depends(get_tenant), db: Session = Depends(get_db), actor: User = Depends(staff_only),
):
    service = TabService(db, tenant.id)
    return service.to_response(service.resolve_payment(tab_id, payment_id, True, actor), tenant)


@router.post("/{tab_id}/payments/{payment_id}/reject", response_model=TabResponse)
def reject_tab_payment(
    tab_id: UUID, payment_id: UUID, tenant: Tenant = Depends(get_tenant), db: Session = Depends(get_db), actor: User = Depends(staff_only),
):
    service = TabService(db, tenant.id)
    return service.to_response(service.resolve_payment(tab_id, payment_id, False, actor), tenant)


@router.post("/{tab_id}/cancel", response_model=TabResponse)
def cancel_tab(
    tab_id: UUID, data: TabReason, tenant: Tenant = Depends(get_tenant), db: Session = Depends(get_db), actor: User = Depends(staff_only),
):
    service = TabService(db, tenant.id)
    return service.to_response(service.cancel(tab_id, data.reason, actor), tenant)
