import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

logger = logging.getLogger(__name__)


class NotFoundError(ValueError):
    pass


class BusinessRuleError(ValueError):
    pass


class AuthenticationError(ValueError):
    pass


class PlanLimitError(ValueError):
    """The tenant's plan does not allow this; the frontend turns `code` into an upgrade prompt."""

    def __init__(self, message: str, feature: str):
        super().__init__(message)
        self.feature = feature


# Unique constraint name -> message shown to the user.
_CONFLICT_MESSAGES = {
    "uq_categories_tenant_name": "Já existe uma categoria com esse nome.",
    "uq_users_tenant_email": "Já existe um usuário com esse e-mail.",
    "uq_customers_tenant_phone_digits": "Já existe um cliente com esse telefone.",
    "uq_coupons_tenant_code": "Já existe um cupom com esse código.",
    "tenants_slug_key": "Este endereço já está em uso. Escolha outro.",
}


# Field names (API) -> labels shown to people.
_FIELD_LABELS = {
    "email": "E-mail", "username": "E-mail", "password": "Senha", "new_password": "Nova senha",
    "current_password": "Senha atual", "business_name": "Nome do estabelecimento", "admin_name": "Seu nome",
    "customer_name": "Nome", "customer_phone": "Telefone", "phone": "Telefone", "slug": "Endereço", "name": "Nome",
    "price": "Preço", "quantity": "Quantidade", "table_label": "Mesa", "code": "Código", "reason": "Motivo",
    "description": "Descrição", "notes": "Observações", "delivery_address": "Endereço de entrega", "value": "Valor",
    "items": "Itens", "token": "Link", "split_count": "Pessoas", "payment_method": "Forma de pagamento",
}


def _translate(error: dict) -> str:
    """Pydantic messages are English; people get Portuguese, with the field name when it helps."""
    kind, ctx = error.get("type", ""), error.get("ctx") or {}
    message = str(error.get("msg", ""))
    if kind == "value_error":
        text = message.removeprefix("Value error, ")
        # email-validator explains in English why an address is invalid.
        return "Informe um e-mail válido." if "email address" in text.lower() or "valid email" in text.lower() else text
    texts = {
        "missing": "preencha este campo.",
        "string_too_short": f"use pelo menos {ctx.get('min_length')} caracteres.",
        "string_too_long": f"use no máximo {ctx.get('max_length')} caracteres.",
        "too_short": f"adicione pelo menos {ctx.get('min_length')} item(ns).",
        "too_long": f"no máximo {ctx.get('max_length')} itens.",
        "greater_than": f"deve ser maior que {ctx.get('gt')}.",
        "greater_than_equal": f"deve ser no mínimo {ctx.get('ge')}.",
        "less_than": f"deve ser menor que {ctx.get('lt')}.",
        "less_than_equal": f"deve ser no máximo {ctx.get('le')}.",
        "int_parsing": "informe um número inteiro.", "decimal_parsing": "informe um valor válido.",
        "float_parsing": "informe um número válido.", "uuid_parsing": "identificador inválido.",
        "enum": "opção inválida.", "literal_error": "opção inválida.", "bool_parsing": "valor inválido.",
        "string_pattern_mismatch": "formato inválido.", "decimal_max_places": "use no máximo 2 casas decimais.",
        "json_invalid": "dados inválidos.",
    }
    text = texts.get(kind)
    if text is None:
        return "Dados inválidos. Confira os campos e tente novamente."
    field = next((str(part) for part in reversed(error.get("loc", ())) if isinstance(part, str)), "")
    label = _FIELD_LABELS.get(field)
    return f"{label}: {text}" if label else text[0].upper() + text[1:]


def _error(status_code: int, detail: str, headers: dict[str, str] | None = None) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"detail": detail}, headers=headers)


def register_exception_handlers(app: FastAPI) -> None:

    @app.exception_handler(AuthenticationError)
    async def authentication_handler(request: Request, exc: AuthenticationError):
        return _error(status.HTTP_401_UNAUTHORIZED, str(exc), {"WWW-Authenticate": "Bearer"})

    @app.exception_handler(BusinessRuleError)
    async def business_rule_handler(request: Request, exc: BusinessRuleError):
        return _error(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc))

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError):
        detail = [{"loc": list(e.get("loc", ())), "msg": _translate(e), "type": e.get("type")} for e in exc.errors()]
        return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, content={"detail": detail})

    @app.exception_handler(PlanLimitError)
    async def plan_limit_handler(request: Request, exc: PlanLimitError):
        return JSONResponse(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            content={"detail": str(exc), "code": "PLAN_LIMIT", "feature": exc.feature},
        )

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
