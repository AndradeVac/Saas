"""Platform panel (for the owner of Mesa Digital): every store, MRR, trials ending, stores without orders."""
import hmac
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.plans import PLANS
from app.models.order import Order, OrderStatus
from app.models.tenant import Tenant, TenantStatus
from app.models.user import User, UserRole

router = APIRouter(prefix="/platform/admin", tags=["Platform admin"])


def platform_admin(x_admin_token: str | None = Header(default=None)) -> None:
    if not settings.platform_admin_token or not x_admin_token or not hmac.compare_digest(x_admin_token, settings.platform_admin_token):
        raise HTTPException(status_code=404, detail="Não encontrado.")  # the panel does not even admit it exists


@router.get("/overview", dependencies=[Depends(platform_admin)])
def overview(db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc)
    week = now - timedelta(days=7)
    orders_week = dict(db.execute(select(Order.tenant_id, func.count(Order.id)).where(Order.created_at >= week, Order.status != OrderStatus.CANCELLED).group_by(Order.tenant_id)).all())
    orders_total = dict(db.execute(select(Order.tenant_id, func.count(Order.id)).group_by(Order.tenant_id)).all())
    last_order = dict(db.execute(select(Order.tenant_id, func.max(Order.created_at)).group_by(Order.tenant_id)).all())
    owners = {row[0]: row for row in db.execute(select(User.tenant_id, User.name, User.email).where(User.role == UserRole.ADMIN).order_by(User.created_at))}
    stores, mrr = [], Decimal(0)
    for tenant in db.scalars(select(Tenant).order_by(Tenant.created_at.desc())):
        paying = tenant.billing_status == "ACTIVE" or (tenant.status is TenantStatus.ACTIVE and tenant.billing_status == "NONE" and tenant.plan in PLANS and tenant.plan != "trial")
        price = PLANS.get(tenant.plan, PLANS["trial"]).price
        monthly = (price * 10 / 12 if tenant.billing_cycle == "YEARLY" else price) if paying else Decimal(0)
        mrr += monthly
        owner = owners.get(tenant.id)
        stores.append({
            "slug": tenant.slug, "name": tenant.name.strip(), "status": tenant.status.value, "plan": tenant.plan,
            "billing_status": tenant.billing_status, "billing_cycle": tenant.billing_cycle, "paid_until": tenant.paid_until,
            "trial_ends_at": tenant.trial_ends_at, "created_at": tenant.created_at, "phone": tenant.phone,
            "owner_name": owner[1] if owner else None, "owner_email": owner[2] if owner else None,
            "orders_7d": int(orders_week.get(tenant.id, 0)), "orders_total": int(orders_total.get(tenant.id, 0)),
            "last_order_at": last_order.get(tenant.id), "monthly_value": round(monthly, 2), "referred_by": tenant.referred_by,
        })
    trials = [s for s in stores if s["status"] == "TRIAL"]
    return {
        "mrr": round(mrr, 2),
        "stores": len(stores),
        "paying": sum(1 for s in stores if s["monthly_value"] > 0),
        "trials": len(trials),
        "trials_ending_3d": sum(1 for s in trials if s["trial_ends_at"] and now <= s["trial_ends_at"] <= now + timedelta(days=3)),
        "no_orders_7d": sum(1 for s in stores if s["orders_7d"] == 0 and s["status"] != "SUSPENDED"),
        "overdue": sum(1 for s in stores if s["billing_status"] == "OVERDUE"),
        "list": stores,
    }
