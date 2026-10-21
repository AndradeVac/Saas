import csv
import io
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.plans import EXPORTS, require_feature
from app.core.security import staff_only
from app.models.user import User
from app.schemas.common import Page
from app.schemas.customer import CustomerCreate, CustomerListItem, CustomerResponse, CustomerUpdate
from app.services.customer import CustomerService

router = APIRouter(prefix="/customers", tags=["Customers"])


@router.post("", response_model=CustomerResponse, status_code=201)
def create_customer(data: CustomerCreate, db: Session = Depends(get_db), actor: User = Depends(staff_only)):
    return CustomerService(db, actor.tenant_id).create(data)


@router.get("", response_model=Page[CustomerListItem])
def list_customers(
    q: str | None = Query(default=None, max_length=80),
    active: bool | None = None,
    sort: str = Query(default="name", pattern="^(name|recent|spent)$"),
    page: int = Query(default=1, ge=1, le=10_000),
    page_size: int = Query(default=25, ge=1, le=200),
    db: Session = Depends(get_db),
    actor: User = Depends(staff_only),
):
    items, total = CustomerService(db, actor.tenant_id).search(q, active, page, page_size, sort)
    return Page(items=items, total=total, page=page, page_size=page_size)


@router.get("/export", dependencies=[Depends(require_feature(EXPORTS))])
def export_customers(db: Session = Depends(get_db), actor: User = Depends(staff_only)):
    items, _ = CustomerService(db, actor.tenant_id).search(None, True, 1, 5000, "name")
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";")
    writer.writerow(["Nome", "Telefone", "Pedidos", "Total gasto", "Último pedido", "Observações"])
    for c in items:
        writer.writerow([
            c.name, c.phone or "", c.orders_count, f"{c.total_spent:.2f}".replace(".", ","),
            c.last_order_at.strftime("%d/%m/%Y") if c.last_order_at else "", c.notes or "",
        ])
    return Response(
        content=buffer.getvalue().encode("utf-8-sig"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=clientes.csv"},
    )


@router.get("/{customer_id}", response_model=CustomerResponse)
def get_customer(customer_id: UUID, db: Session = Depends(get_db), actor: User = Depends(staff_only)):
    return CustomerService(db, actor.tenant_id).get_by_id(customer_id)


@router.patch("/{customer_id}", response_model=CustomerResponse)
def update_customer(
    customer_id: UUID,
    data: CustomerUpdate,
    db: Session = Depends(get_db),
    actor: User = Depends(staff_only),
):
    return CustomerService(db, actor.tenant_id).update(customer_id, data)
