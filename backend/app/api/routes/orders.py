from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import staff_only
from app.models.user import User
from app.schemas.order import OrderCreate, OrderPaymentUpdate, OrderResponse, OrderStatusUpdate
from app.services.order import OrderService

router = APIRouter(prefix="/orders", tags=["Orders"])


@router.post("", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
def create_order(data: OrderCreate, db: Session = Depends(get_db), actor: User = Depends(staff_only)):
    return OrderService(db, actor.tenant_id).create(data, actor)


@router.get("", response_model=list[OrderResponse])
def get_orders(
    limit: int = Query(default=200, ge=1, le=1000),
    db: Session = Depends(get_db),
    actor: User = Depends(staff_only),
):
    return OrderService(db, actor.tenant_id).get_all(limit=limit)


@router.get("/{order_id}", response_model=OrderResponse)
def get_order(order_id: UUID, db: Session = Depends(get_db), actor: User = Depends(staff_only)):
    return OrderService(db, actor.tenant_id).get_by_id(order_id)


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
