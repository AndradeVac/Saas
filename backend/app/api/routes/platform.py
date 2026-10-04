"""Endpoints of the platform itself (no tenant yet): self-service sign-up."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.rate_limit import signup_rate_limit, slug_check_rate_limit
from app.schemas.tenant import SignupRequest, SignupResponse, SlugAvailability
from app.services.tenant import TenantService

router = APIRouter(prefix="/platform", tags=["Platform"])


@router.get("/slug-available", response_model=SlugAvailability, dependencies=[Depends(slug_check_rate_limit)])
def slug_available(slug: str = Query(min_length=1, max_length=60), db: Session = Depends(get_db)):
    return TenantService(db).check_slug(slug)


@router.post("/signup", response_model=SignupResponse, status_code=201, dependencies=[Depends(signup_rate_limit)])
def signup(data: SignupRequest, db: Session = Depends(get_db)):
    tenant = TenantService(db).signup(data)
    return SignupResponse(
        slug=tenant.slug,
        name=tenant.name,
        url=settings.tenant_url(tenant.slug, "/"),
        login_url=settings.tenant_url(tenant.slug, "/login"),
    )
