from decimal import Decimal

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import BusinessRuleError
from app.core.pix import brcode, is_valid_pix_key, normalize_pix_key
from app.core.plans import plan_status, public_tenant
from app.core.security import admin_only, staff_only
from app.core.tenancy import get_tenant
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.plan import TenantPlanStatus
from app.schemas.tab import PixCode
from app.schemas.tenant import PublicTenant, TenantSettingsResponse, TenantSettingsUpdate
from app.services.tenant import TenantService

router = APIRouter(prefix="/tenant", tags=["Tenant"])


@router.get("", response_model=PublicTenant)
def get_public_tenant(response: Response, tenant: Tenant = Depends(get_tenant), db: Session = Depends(get_db)):
    """Name, logo and colors of the business whose address is being visited."""
    response.headers["Cache-Control"] = "no-store"
    return public_tenant(db, tenant)


@router.get("/plan", response_model=TenantPlanStatus)
def get_plan(tenant: Tenant = Depends(get_tenant), db: Session = Depends(get_db), _: User = Depends(staff_only)):
    """Current plan, trial countdown and usage against the plan limits."""
    return plan_status(db, tenant)


@router.get("/settings", response_model=TenantSettingsResponse)
def get_settings(tenant: Tenant = Depends(get_tenant), _: User = Depends(staff_only)):
    return tenant


@router.patch("/settings", response_model=TenantSettingsResponse)
def update_settings(
    data: TenantSettingsUpdate,
    tenant: Tenant = Depends(get_tenant),
    user: User = Depends(admin_only),
    db: Session = Depends(get_db),
):
    return TenantService(db).update_settings(tenant, data, user)


@router.get("/pix-preview", response_model=PixCode)
def pix_preview(
    key: str = Query(min_length=1, max_length=100),
    amount: Decimal = Query(default=Decimal("1.00"), gt=0, le=1000, max_digits=7, decimal_places=2),
    tenant: Tenant = Depends(get_tenant),
    _: User = Depends(admin_only),
):
    """A test QR Code for the key typed in Settings (saved or not): the owner pays it to check the key works."""
    if not is_valid_pix_key(key):
        raise BusinessRuleError("Chave PIX inválida. Use CPF, CNPJ, e-mail, celular com DDD ou a chave aleatória.")
    return PixCode(code=brcode(normalize_pix_key(key), amount, tenant.name, tenant.city or "BRASIL", "TESTE"), amount=amount)


@router.get("/export")
def export_account(tenant: Tenant = Depends(get_tenant), db: Session = Depends(get_db), _: User = Depends(admin_only)):
    """LGPD portability: everything the store has here, in one JSON file (menu, customers, orders)."""
    import json
    from datetime import datetime, timezone

    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    from app.models.category import Category
    from app.models.customer import Customer
    from app.models.order import Order
    from app.models.product import Product

    def rows(model, *options):
        return db.scalars(select(model).where(model.tenant_id == tenant.id).options(*options)).all()

    data = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "store": TenantSettingsResponse.model_validate(tenant).model_dump(mode="json"),
        "categories": [{"id": str(c.id), "name": c.name, "active": c.active} for c in rows(Category)],
        "products": [{"id": str(p.id), "category_id": str(p.category_id), "name": p.name, "description": p.description, "price": str(p.price),
                      "cost": str(p.cost) if p.cost is not None else None, "active": p.active, "options": p.options} for p in rows(Product)],
        "customers": [{"id": str(c.id), "name": c.name, "phone": c.phone, "notes": c.notes, "marketing_opt_in": c.marketing_opt_in,
                       "created_at": c.created_at.isoformat()} for c in rows(Customer)],
        "orders": [{"number": o.order_number, "created_at": o.created_at.isoformat(), "status": o.status.value, "service": o.service_type.value,
                    "payment": o.payment_method.value, "paid": o.payment_status.value, "customer_id": str(o.customer_id), "total": str(o.total),
                    "items": [{"name": i.product_name, "quantity": i.quantity, "total": str(i.total_price), "options": i.options} for i in o.items]}
                   for o in rows(Order, selectinload(Order.items))],
    }
    return Response(json.dumps(data, ensure_ascii=False, indent=1), media_type="application/json",
                    headers={"Content-Disposition": f"attachment; filename={tenant.slug}-dados.json"})
