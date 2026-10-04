from datetime import datetime, timedelta, timezone
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.exceptions import AuthenticationError
from app.core.tenancy import get_tenant
from app.models.tenant import Tenant
from app.models.user import User, UserRole
from app.repositories.user import UserRepository


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def create_access_token(user: User) -> str:
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {
        "sub": str(user.id),
        "tid": str(user.tenant_id),
        "role": user.role.value,
        "exp": expires_at,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def get_current_user(
    token: str = Depends(oauth2_scheme),
    tenant: Tenant = Depends(get_tenant),
    db: Session = Depends(get_db),
) -> User:
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        user_id = UUID(payload["sub"])
        token_tenant_id = UUID(payload["tid"])
    except (KeyError, TypeError, ValueError, jwt.InvalidTokenError) as error:
        raise AuthenticationError("Token inválido ou expirado.") from error

    # A token only works on the tenant it was issued for.
    if token_tenant_id != tenant.id:
        raise AuthenticationError("Token inválido ou expirado.")

    user = UserRepository(db, tenant.id).get_by_id(user_id)
    if user is None:
        raise AuthenticationError("Usuário não encontrado ou inativo.")
    return user


def require_roles(*allowed_roles: UserRole):
    def role_dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Usuário sem permissão para este recurso.",
            )
        return user

    return role_dependency


staff_only = require_roles(UserRole.ADMIN, UserRole.OPERATOR)
admin_only = require_roles(UserRole.ADMIN)
