"""Subscription billing: the owner subscribes/cancels; Asaas notifies payments through the webhook."""
import hmac

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.security import admin_only
from app.core.tenancy import get_tenant
from app.models.tenant import Tenant
from app.models.user import User
from app.services.billing import BillingService

router = APIRouter(prefix="/billing", tags=["Billing"])


class SubscribeRequest(BaseModel):
    plan: str = Field(min_length=2, max_length=30)
    document: str = Field(min_length=11, max_length=20)  # CPF or CNPJ of whoever pays
    email: EmailStr


class CheckoutResponse(BaseModel):
    checkout_url: str | None


@router.post("/subscribe", response_model=CheckoutResponse)
def subscribe(data: SubscribeRequest, tenant: Tenant = Depends(get_tenant), db: Session = Depends(get_db), actor: User = Depends(admin_only)):
    """Creates (or changes) the subscription and returns Asaas' payment page (PIX, boleto or card)."""
    return CheckoutResponse(checkout_url=BillingService(db).subscribe(tenant, actor, data.plan, data.document, str(data.email)))


@router.post("/pay", response_model=CheckoutResponse)
def pay(tenant: Tenant = Depends(get_tenant), db: Session = Depends(get_db), _: User = Depends(admin_only)):
    """Payment page of the open charge (first payment or an overdue one)."""
    return CheckoutResponse(checkout_url=BillingService(db).payment_url(tenant))


@router.post("/cancel", status_code=status.HTTP_204_NO_CONTENT)
def cancel(tenant: Tenant = Depends(get_tenant), db: Session = Depends(get_db), actor: User = Depends(admin_only)):
    BillingService(db).cancel(tenant, actor)


@router.post("/webhook", include_in_schema=False)
async def webhook(request: Request, db: Session = Depends(get_db), asaas_access_token: str | None = Header(default=None)):
    """Asaas payment notifications. Authenticated by the secret token configured on the webhook."""
    expected = settings.asaas_webhook_token
    if not expected or not asaas_access_token or not hmac.compare_digest(asaas_access_token, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="unauthorized")
    result = BillingService(db).handle_webhook(await request.json())
    return {"received": True, "result": result}
