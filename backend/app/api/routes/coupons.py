from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.plans import COUPONS, require_feature
from app.core.security import admin_only
from app.models.user import User
from app.schemas.coupon import CouponCreate, CouponResponse, CouponUpdate
from app.services.coupon import CouponService

router = APIRouter(prefix="/coupons", tags=["Coupons"], dependencies=[Depends(require_feature(COUPONS))])


@router.get("", response_model=list[CouponResponse])
def list_coupons(db: Session = Depends(get_db), actor: User = Depends(admin_only)):
    return CouponService(db, actor.tenant_id).get_all()


@router.post("", response_model=CouponResponse, status_code=status.HTTP_201_CREATED)
def create_coupon(data: CouponCreate, db: Session = Depends(get_db), actor: User = Depends(admin_only)):
    return CouponService(db, actor.tenant_id).create(data, actor)


@router.patch("/{coupon_id}", response_model=CouponResponse)
def update_coupon(coupon_id: UUID, data: CouponUpdate, db: Session = Depends(get_db), actor: User = Depends(admin_only)):
    return CouponService(db, actor.tenant_id).update(coupon_id, data, actor)


@router.delete("/{coupon_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_coupon(coupon_id: UUID, db: Session = Depends(get_db), actor: User = Depends(admin_only)):
    CouponService(db, actor.tenant_id).delete(coupon_id, actor)
