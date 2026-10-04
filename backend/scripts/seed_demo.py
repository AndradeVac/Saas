"""Create (or refresh) a demo account with a ready-made menu, for local development only.

Usage (from backend/):
    python -m scripts.seed_demo

Address: http://demo.localhost:5173   |   login: DEMO_EMAIL / DEMO_PASSWORD below.
These are throwaway development credentials: the script refuses to run in production.
Running it again only adds what is missing (idempotent).
"""
from __future__ import annotations

import sys
from decimal import Decimal

from sqlalchemy import select

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.category import Category
from app.models.product import Product
from app.models.tenant import BusinessType, Tenant
from app.schemas.tenant import SignupRequest
from app.services.tenant import TenantService

DEMO_SLUG = "demo"
DEMO_EMAIL = "admin@demo.com"
DEMO_PASSWORD = "demo12345"

# category -> [(name, description, price, featured)]
MENU: dict[str, list[tuple[str, str, str, bool]]] = {
    "Pães": [
        ("Pão francês (un.)", "Crocante por fora, macio por dentro, assado a cada hora.", "0.90", False),
        ("Pão de queijo", "Receita mineira, bem quentinho.", "4.50", True),
        ("Baguete artesanal", "Fermentação natural de 24 horas.", "12.00", False),
        ("Pão de forma integral", "Fatiado, 500 g.", "14.90", False),
    ],
    "Doces e bolos": [
        ("Bolo de cenoura com chocolate", "Fatia generosa com cobertura de brigadeiro.", "9.50", True),
        ("Torta de limão", "Massa amanteigada e merengue maçaricado.", "11.00", False),
        ("Brigadeiro gourmet", "Chocolate belga.", "5.00", False),
    ],
    "Salgados": [
        ("Coxinha de frango", "Massa leve e recheio cremoso com catupiry.", "8.00", True),
        ("Pastel de forno", "Carne, queijo ou frango.", "7.50", False),
        ("Misto quente", "Presunto e queijo no pão de forma.", "10.00", False),
    ],
    "Bebidas": [
        ("Café expresso", "Grãos selecionados, torra média.", "5.00", False),
        ("Cappuccino", "Com espuma de leite e canela.", "9.00", False),
        ("Suco de laranja natural", "300 ml, sem açúcar.", "8.50", False),
        ("Água mineral", "500 ml.", "3.50", False),
    ],
}


def main() -> int:
    if settings.is_production:
        sys.exit("seed_demo não roda em produção.")

    with SessionLocal() as db:
        service = TenantService(db)
        tenant = db.scalar(select(Tenant).where(Tenant.slug == DEMO_SLUG))
        if tenant is None:
            tenant = service.signup(SignupRequest(
                business_name="Padaria Demo",
                business_type=BusinessType.BAKERY,
                slug=DEMO_SLUG,
                phone="11999990000",
                admin_name="Administrador Demo",
                email=DEMO_EMAIL,
                password=DEMO_PASSWORD,
            ))
            print("Conta demo criada.")

        categories = {
            category.name: category
            for category in db.scalars(select(Category).where(Category.tenant_id == tenant.id))
        }
        existing = set(db.scalars(select(Product.name).where(Product.tenant_id == tenant.id)))
        created = 0
        for category_name, items in MENU.items():
            category = categories.get(category_name)
            if category is None:
                category = Category(tenant_id=tenant.id, name=category_name)
                db.add(category)
                db.flush()
            for name, description, price, featured in items:
                if name in existing:
                    continue
                db.add(Product(
                    tenant_id=tenant.id,
                    category_id=category.id,
                    name=name,
                    description=description,
                    price=Decimal(price),
                    featured=featured,
                ))
                created += 1
        db.commit()

    print(f"{created} produtos adicionados.")
    print(f"Cardápio: {settings.tenant_url(DEMO_SLUG, '/')}")
    print(f"Painel:   {settings.tenant_url(DEMO_SLUG, '/login')}  ({DEMO_EMAIL} / {DEMO_PASSWORD})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
