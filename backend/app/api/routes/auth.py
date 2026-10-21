from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rate_limit import login_rate_limit, password_reset_rate_limit
from app.core.security import create_access_token, get_current_user
from app.core.tenancy import get_tenant
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.user import ForgotPasswordRequest, PasswordChange, ResetPasswordRequest, TokenResponse, UserResponse
from app.services.password_reset import PasswordResetService
from app.services.user import UserService

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=TokenResponse, dependencies=[Depends(login_rate_limit)])
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    tenant: Tenant = Depends(get_tenant),
    db: Session = Depends(get_db),
):
    user = UserService(db, tenant.id).authenticate(form_data.username, form_data.password)
    return TokenResponse(access_token=create_access_token(user))


@router.get("/me", response_model=UserResponse)
def current_user(user: User = Depends(get_current_user)):
    return user


@router.post("/password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    data: PasswordChange,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    UserService(db, user.tenant_id).change_password(user, data)


@router.post("/forgot-password", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(password_reset_rate_limit)])
def forgot_password(data: ForgotPasswordRequest, tenant: Tenant = Depends(get_tenant), db: Session = Depends(get_db)):
    """Sends a reset link if the e-mail belongs to this business; answers the same either way."""
    PasswordResetService(db, tenant).request(str(data.email))


@router.post("/reset-password", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(password_reset_rate_limit)])
def reset_password(data: ResetPasswordRequest, tenant: Tenant = Depends(get_tenant), db: Session = Depends(get_db)):
    PasswordResetService(db, tenant).reset(data.token, data.new_password)
