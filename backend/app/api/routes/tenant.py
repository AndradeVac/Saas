from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import admin_only, staff_only
from app.core.tenancy import get_tenant
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.tenant import PublicTenant, TenantSettingsResponse, TenantSettingsUpdate
from app.services.tenant import TenantService

router = APIRouter(prefix="/tenant", tags=["Tenant"])


@router.get("", response_model=PublicTenant)
def get_public_tenant(tenant: Tenant = Depends(get_tenant)):
    """Name, logo and colors of the business whose address is being visited."""
    return tenant


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
