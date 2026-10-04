"""Create a new customer account (tenant + first administrator) from the command line.

Usage (from backend/):
    python -m scripts.create_tenant --slug padaria-do-ze --name "Padaria do Zé" \
        --type BAKERY --email ze@padaria.com --admin-name "José"

The password is asked interactively. For non-interactive environments set ADMIN_PASSWORD.
The same flow is available to customers at /cadastro on the platform's root domain.
"""
from __future__ import annotations

import argparse
import getpass
import os
import sys

from pydantic import ValidationError

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.exceptions import BusinessRuleError
from app.models.tenant import BusinessType
from app.schemas.tenant import SignupRequest
from app.services.tenant import TenantService

MIN_PASSWORD_LENGTH = 8


def read_password() -> str:
    password = os.getenv("ADMIN_PASSWORD")
    if password:
        return password
    password = getpass.getpass("Senha do administrador: ")
    if password != getpass.getpass("Confirme a senha: "):
        sys.exit("As senhas não conferem.")
    return password


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--slug", required=True, help="endereço: <slug>.<domínio>")
    parser.add_argument("--name", required=True, help="nome do estabelecimento")
    parser.add_argument("--type", default="RESTAURANT", choices=[t.value for t in BusinessType])
    parser.add_argument("--email", required=True)
    parser.add_argument("--admin-name", default="Administrador")
    parser.add_argument("--phone")
    args = parser.parse_args()

    password = read_password()
    if len(password) < MIN_PASSWORD_LENGTH:
        sys.exit(f"A senha precisa ter pelo menos {MIN_PASSWORD_LENGTH} caracteres.")

    try:
        request = SignupRequest(
            business_name=args.name,
            business_type=BusinessType(args.type),
            slug=args.slug,
            phone=args.phone,
            admin_name=args.admin_name,
            email=args.email,
            password=password,
        )
    except ValidationError as error:
        sys.exit("; ".join(item["msg"] for item in error.errors()))

    with SessionLocal() as db:
        try:
            tenant = TenantService(db).signup(request)
        except BusinessRuleError as error:
            sys.exit(str(error))

    print(f"Conta criada: {tenant.name}")
    print(f"Endereço: {settings.tenant_url(tenant.slug, '/')}")
    print(f"Painel:   {settings.tenant_url(tenant.slug, '/login')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
