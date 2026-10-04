import logging

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

logger = logging.getLogger(__name__)


class NotFoundError(ValueError):
    pass


class BusinessRuleError(ValueError):
    pass


class AuthenticationError(ValueError):
    pass


# Unique constraint name -> message shown to the user.
_CONFLICT_MESSAGES = {
    "uq_categories_tenant_name": "Já existe uma categoria com esse nome.",
    "uq_users_tenant_email": "Já existe um usuário com esse e-mail.",
    "tenants_slug_key": "Este endereço já está em uso. Escolha outro.",
}


def _error(status_code: int, detail: str, headers: dict[str, str] | None = None) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"detail": detail}, headers=headers)


def register_exception_handlers(app: FastAPI) -> None:

    @app.exception_handler(AuthenticationError)
    async def authentication_handler(request: Request, exc: AuthenticationError):
        return _error(status.HTTP_401_UNAUTHORIZED, str(exc), {"WWW-Authenticate": "Bearer"})

    @app.exception_handler(BusinessRuleError)
    async def business_rule_handler(request: Request, exc: BusinessRuleError):
        return _error(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc))

    @app.exception_handler(NotFoundError)
    async def not_found_handler(request: Request, exc: NotFoundError):
        return _error(status.HTTP_404_NOT_FOUND, str(exc))

    @app.exception_handler(IntegrityError)
    async def integrity_error_handler(request: Request, exc: IntegrityError):
        error = str(exc.orig)
        for constraint, message in _CONFLICT_MESSAGES.items():
            if constraint in error:
                return _error(status.HTTP_409_CONFLICT, message)
        logger.warning("Integrity error on %s %s: %s", request.method, request.url.path, error)
        return _error(status.HTTP_409_CONFLICT, "Não foi possível concluir a operação por conflito de dados.")

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception):
        logger.error("Unhandled error on %s %s", request.method, request.url.path, exc_info=exc)
        return _error(status.HTTP_500_INTERNAL_SERVER_ERROR, "Erro interno. Tente novamente em instantes.")
