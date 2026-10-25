"""Endpoints of the platform itself (no tenant yet): self-service sign-up."""
from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import allow_all_tenants, get_db
from app.core.plans import plan_catalog
from app.core.rate_limit import signup_rate_limit, slug_check_rate_limit
from app.schemas.plan import PlanCatalog
from app.schemas.tenant import SignupRequest, SignupResponse, SlugAvailability
from app.services import lifecycle
from app.services.access_log import record_access
from app.services.tenant import TenantService

router = APIRouter(prefix="/platform", tags=["Platform"])


@router.get("/slug-available", response_model=SlugAvailability, dependencies=[Depends(slug_check_rate_limit)])
def slug_available(slug: str = Query(min_length=1, max_length=60), db: Session = Depends(get_db)):
    return TenantService(db).check_slug(slug)


@router.get("/plans", response_model=PlanCatalog)
def list_plans():
    """Pricing table shown on the landing page and on the panel's upgrade screen."""
    return plan_catalog()


@router.post("/signup", response_model=SignupResponse, status_code=201, dependencies=[Depends(signup_rate_limit)])
def signup(data: SignupRequest, request: Request, background: BackgroundTasks, db: Session = Depends(get_db)):
    allow_all_tenants(db)  # the store does not exist yet: it is created here, with its owner and first category
    tenant = TenantService(db).signup(data)
    record_access(db, request, "SIGNUP", tenant.id)
    background.add_task(lifecycle.welcome, tenant.id)
    return SignupResponse(
        slug=tenant.slug,
        name=tenant.name,
        url=settings.tenant_url(tenant.slug, "/"),
        login_url=settings.tenant_url(tenant.slug, "/login"),
    )
