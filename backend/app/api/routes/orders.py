import csv
import io
from datetime import date, datetime, time, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.plans import EXPORTS, require_feature
from app.core.security import staff_only
from app.core.tenancy import get_tenant
from app.models.order import OrderStatus, PaymentStatus, ServiceType
from app.models.tenant import Tenant
from app.models.user import User
from app.repositories.order import OrderRepository
from app.schemas.common import Page
from app.schemas.order import (
    OrderCreate,
    OrderEdit,
    OrderPaymentUpdate,
    OrderResponse,
    OrderStatusUpdate,
)
from app.services.order import OrderService

router = APIRouter(prefix="/orders", tags=["Orders"])

_SERVICE_LABELS = {"DINE_IN": "No local", "TAKEAWAY": "Para levar", "DELIVERY": "Entrega"}
_STATUS_LABELS = {
    "RECEIVED": "Recebido", "PREPARING": "Em preparo", "READY": "Pronto", "FINISHED": "Entregue", "CANCELLED": "Cancelado",
}


def _bounds(tenant: Tenant, date_from: date | None, date_to: date | None) -> tuple[datetime | None, datetime | None]:
    """Inclusive dates in the tenant's time zone -> [start, end) instants."""
    zone = ZoneInfo(tenant.timezone)
    start = datetime.combine(date_from, time.min, tzinfo=zone) if date_from else None
    end = datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=zone) if date_to else None
    return start, end


@router.post("", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
def create_order(data: OrderCreate, db: Session = Depends(get_db), actor: User = Depends(staff_only)):
    return OrderService(db, actor.tenant_id).create(data, actor)


@router.get("/board", response_model=list[OrderResponse])
def get_board(tenant: Tenant = Depends(get_tenant), db: Session = Depends(get_db), actor: User = Depends(staff_only)):
    """Orders in progress plus today's finished/cancelled ones: what the kitchen screen shows."""
    zone = ZoneInfo(tenant.timezone)
    day_start = datetime.combine(datetime.now(zone).date(), time.min, tzinfo=zone)
    return OrderRepository(db, tenant.id).get_board(day_start)


@router.get("", response_model=Page[OrderResponse])
def list_orders(
    status_in: list[OrderStatus] | None = Query(default=None, alias="status"),
    payment_status: PaymentStatus | None = None,
    service_type: ServiceType | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    q: str | None = Query(default=None, max_length=80),
    page: int = Query(default=1, ge=1, le=10_000),
    page_size: int = Query(default=25, ge=1, le=100),
    tenant: Tenant = Depends(get_tenant),
    db: Session = Depends(get_db),
    _: User = Depends(staff_only),
):
    start, end = _bounds(tenant, date_from, date_to)
    items, total = OrderRepository(db, tenant.id).search(
        status=status_in, payment_status=payment_status, service_type=service_type,
        date_from=start, date_to=end, q=q, page=page, page_size=page_size,
    )
    return Page(items=items, total=total, page=page, page_size=page_size)


@router.get("/export", dependencies=[Depends(require_feature(EXPORTS))])
def export_orders(
    status_in: list[OrderStatus] | None = Query(default=None, alias="status"),
    payment_status: PaymentStatus | None = None,
    service_type: ServiceType | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    q: str | None = Query(default=None, max_length=80),
    tenant: Tenant = Depends(get_tenant),
    db: Session = Depends(get_db),
    _: User = Depends(staff_only),
):
    start, end = _bounds(tenant, date_from, date_to)
    orders = OrderRepository(db, tenant.id).export(
        status=status_in, payment_status=payment_status, service_type=service_type, date_from=start, date_to=end, q=q,
    )
    zone = ZoneInfo(tenant.timezone)
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";")
    writer.writerow(["Pedido", "Data", "Cliente", "Telefone", "Atendimento", "Mesa", "Status", "Pagamento", "Forma",
                     "Itens", "Subtotal", "Desconto", "Taxa de serviço", "Entrega", "Total"])
    for order in orders:
        def money(value):
            return f"{value:.2f}".replace(".", ",")
        writer.writerow([
            order.order_number,
            order.created_at.astimezone(zone).strftime("%d/%m/%Y %H:%M"),
            order.customer_name or "",
            order.customer_phone or "",
            _SERVICE_LABELS.get(order.service_type.value, order.service_type.value),
            order.table_label or "",
            _STATUS_LABELS.get(order.status.value, order.status.value),
            "Pago" if order.payment_status is PaymentStatus.PAID else "Pendente",
            order.payment_method.value,
            "; ".join(f"{i.quantity}x {i.product_name}" for i in order.items),
            money(order.subtotal), money(order.discount), money(order.service_fee), money(order.delivery_fee), money(order.total),
        ])
    # utf-8-sig so Excel opens accents correctly.
    return Response(
        content=buffer.getvalue().encode("utf-8-sig"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={tenant.slug}-pedidos.csv"},
    )


@router.get("/{order_id}", response_model=OrderResponse)
def get_order(order_id: UUID, db: Session = Depends(get_db), actor: User = Depends(staff_only)):
    return OrderService(db, actor.tenant_id).get_by_id(order_id)


@router.patch("/{order_id}", response_model=OrderResponse)
def edit_order(order_id: UUID, data: OrderEdit, db: Session = Depends(get_db), actor: User = Depends(staff_only)):
    return OrderService(db, actor.tenant_id).edit(order_id, data, actor)


@router.patch("/{order_id}/status", response_model=OrderResponse)
def update_order_status(
    order_id: UUID,
    data: OrderStatusUpdate,
    db: Session = Depends(get_db),
    actor: User = Depends(staff_only),
):
    return OrderService(db, actor.tenant_id).update_status(order_id, data, actor)


@router.patch("/{order_id}/payment", response_model=OrderResponse)
def update_order_payment(
    order_id: UUID,
    data: OrderPaymentUpdate,
    db: Session = Depends(get_db),
    actor: User = Depends(staff_only),
):
    return OrderService(db, actor.tenant_id).update_payment(order_id, data, actor)
