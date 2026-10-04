"""Tenant resolution.

The frontend derives the tenant from the subdomain it is served on (<slug>.<root domain>)
and sends it in the `X-Tenant` header. Every route that touches tenant data depends on
`get_tenant`; staff routes additionally check that the JWT was issued for that same tenant
(see `app.core.security.get_current_user`), so a token can never be replayed on another tenant.
"""
import re

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import NotFoundError
from app.models.tenant import Tenant, TenantStatus
from app.repositories.tenant import TenantRepository

SLUG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{1,38}[a-z0-9]$")

# Subdomains that must never be handed to a customer (infrastructure, brand, abuse-prone names).
RESERVED_SLUGS = frozenset({
    "www", "app", "api", "admin", "painel", "dashboard", "login", "entrar", "cadastro", "signup", "register",
    "platform", "plataforma", "static", "assets", "cdn", "mail", "email", "smtp", "ftp", "ns1", "ns2",
    "suporte", "support", "ajuda", "help", "status", "docs", "blog", "billing", "pagamento", "pagamentos",
    "mesa", "mesadigital", "cardapio", "root", "test", "teste", "staging", "dev", "demo-admin",
})


def normalize_slug(value: str | None) -> str:
    return (value or "").strip().lower()


def get_tenant(
    x_tenant: str | None = Header(default=None, alias="X-Tenant"),
    db: Session = Depends(get_db),
) -> Tenant:
    slug = normalize_slug(x_tenant)
    tenant = TenantRepository(db).get_by_slug(slug) if SLUG_PATTERN.match(slug) else None
    if tenant is None:
        raise NotFoundError("Estabelecimento não encontrado.")
    if tenant.status is TenantStatus.SUSPENDED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Este estabelecimento está temporariamente indisponível.",
        )
    return tenant
