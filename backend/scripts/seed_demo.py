"""Create (or refresh) a demo account with a ready-made menu, for local development only.

Usage (from backend/):
    python -m scripts.seed_demo                    # creates what is missing
    python -m scripts.seed_demo --refresh-photos   # also replaces the demo photos

Creates one account per plan, all with the same menu; each has its own login (see ACCOUNTS below):
    http://demo.localhost:5173            free trial (Degustação)
    http://demo-essencial.localhost:5173  Essencial
    http://demo-pro.localhost:5173        Profissional
These are throwaway development credentials: the script refuses to run in production.
Running it again only adds what is missing (idempotent).

Photos come from Unsplash (free to use under the Unsplash License) and are stored like any upload.
Without internet the menu is created without photos.
"""
from __future__ import annotations

import sys
import urllib.request
from decimal import Decimal

from sqlalchemy import select

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.category import Category
from app.models.coupon import Coupon, CouponKind
from app.models.product import Product
from app.core.plans import PLANS
from app.models.tenant import BusinessType, Tenant, TenantStatus
from app.schemas.tenant import SignupRequest
from app.models.user import User, UserRole
from app.services.media import MediaService
from app.services.tenant import TenantService
from app.services.user import UserService

DEMO_SLUG = "demo"
# One account per plan, so every experience can be tried side by side: (slug, name, plan, e-mail, password).
# Throwaway development credentials; running the script again resets the owner's login to these.
ACCOUNTS = [
    (DEMO_SLUG, "Padaria Demo", "trial", "teste@demo.com", "teste1234"),
    ("demo-essencial", "Padaria Essencial", "essencial", "essencial@demo.com", "essencial123"),
    ("demo-pro", "Padaria Pro", "pro", "pro@demo.com", "profissional123"),
]

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


# Option groups for some products (size / extras), to exercise the product options flow.
OPTIONS: dict[str, list[dict]] = {
    "Cappuccino": [
        {"id": "size", "name": "Tamanho", "required": True, "min": 1, "max": 1, "options": [
            {"id": "p", "name": "Pequeno (200 ml)", "price": "0", "active": True},
            {"id": "g", "name": "Grande (350 ml)", "price": "3.00", "active": True}]},
        {"id": "extra", "name": "Adicionais", "required": False, "min": 0, "max": 2, "options": [
            {"id": "choc", "name": "Chocolate", "price": "2.00", "active": True},
            {"id": "chan", "name": "Chantilly", "price": "2.50", "active": True}]},
    ],
    "Misto quente": [
        {"id": "pao", "name": "Tipo de pão", "required": True, "min": 1, "max": 1, "options": [
            {"id": "f", "name": "Pão de forma", "price": "0", "active": True},
            {"id": "i", "name": "Integral", "price": "1.00", "active": True}]},
    ],
}


# product name -> Unsplash photo id. Products without a faithful photo keep the placeholder on purpose.
PHOTOS: dict[str, str] = {
    "Pão francês (un.)": "1608198093002-ad4e005484ec",
    "Baguete artesanal": "1586444248902-2f64eddc13df",
    "Pão de forma integral": "1549931319-a545dcf3bc73",
    "Bolo de cenoura com chocolate": "1578985545062-69928b1d9587",
    "Torta de limão": "1519915028121-7d3463d20b13",
    "Brigadeiro gourmet": "1606312619070-d48b4c652a52",
    "Pastel de forno": "1601050690597-df0568f70950",
    "Misto quente": "1528735602780-2552fd46c7af",
    "Café expresso": "1559496417-e7f25cb247f3",
    "Cappuccino": "1572442388796-11668a67e53d",
    "Suco de laranja natural": "1600271886742-f049cd451bba",
    "Água mineral": "1548839140-29a749e1cf4d",
}
COVER_PHOTO = "1568254183919-78a4f43a2877"


def _download_photo(media: MediaService, photo_id: str, width: int = 900) -> str | None:
    url = f"https://images.unsplash.com/photo-{photo_id}?w={width}&q=80&fit=crop&auto=format"
    try:
        with urllib.request.urlopen(url, timeout=20) as response:  # noqa: S310 - fixed https host
            return f"/media/{media.save(response.read()).id}"
    except Exception as error:  # offline or photo removed: keep going without it
        print(f"  sem foto ({photo_id}): {error}")
        return None


def add_photos(db, tenant: Tenant, refresh: bool) -> int:
    media = MediaService(db, tenant.id)
    added = 0
    for product in db.scalars(select(Product).where(Product.tenant_id == tenant.id, Product.name.in_(PHOTOS))):
        if product.image_url and not refresh:
            continue
        previous, url = product.image_url, _download_photo(media, PHOTOS[product.name])
        if url:
            product.image_url = url
            media.release_if_orphan(previous)
            added += 1
    if (not tenant.cover_url or refresh) and (url := _download_photo(media, COVER_PHOTO, width=1600)):
        previous, tenant.cover_url = tenant.cover_url, url
        media.release_if_orphan(previous)
    if not tenant.description or tenant.description == "Pães quentinhos todo dia.":
        tenant.description = "Pães de fermentação natural, doces caseiros e café especial. Peça pelo celular e retire no balcão."
    return added


def seed_account(db, slug: str, name: str, plan: str, email: str, password: str, refresh_photos: bool) -> tuple[Tenant, int, int]:
    """Creates (or completes) one demo account and puts it on `plan` ("trial" keeps it in the free trial)."""
    tenant = db.scalar(select(Tenant).where(Tenant.slug == slug))
    if tenant is None:
        tenant = TenantService(db).signup(SignupRequest(
            business_name=name,
            business_type=BusinessType.BAKERY,
            slug=slug,
            phone="11999990000",
            admin_name="Administrador Demo",
            email=email,
            password=password,
        ))
        tenant.address = "Rua das Flores, 100 - Centro"
    if plan != "trial":
        tenant.status, tenant.plan = TenantStatus.ACTIVE, plan

    # The owner (first administrator) always ends up with this account's demo login.
    owner = db.scalar(
        select(User).where(User.tenant_id == tenant.id, User.role == UserRole.ADMIN).order_by(User.created_at).limit(1)
    )
    if owner is not None:
        owner.email, owner.active = email, True
        if not UserService.password_hash.verify(password, owner.password_hash):
            owner.password_hash = UserService.password_hash.hash(password)

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
        for product_name, description, price, featured in items:
            if product_name in existing:
                continue
            db.add(Product(
                tenant_id=tenant.id,
                category_id=category.id,
                name=product_name,
                description=description,
                price=Decimal(price),
                featured=featured,
                options=OPTIONS.get(product_name, []),
            ))
            created += 1
    if db.scalar(select(Coupon).where(Coupon.tenant_id == tenant.id, Coupon.code == "DEMO10")) is None:
        db.add(Coupon(tenant_id=tenant.id, code="DEMO10", kind=CouponKind.PERCENT, value=Decimal("10")))
    db.flush()
    photos = add_photos(db, tenant, refresh=refresh_photos)
    db.commit()
    return tenant, created, photos


def main() -> int:
    if settings.is_production:
        sys.exit("seed_demo não roda em produção.")

    refresh = "--refresh-photos" in sys.argv
    with SessionLocal() as db:
        for slug, name, plan, email, password in ACCOUNTS:
            tenant, created, photos = seed_account(db, slug, name, plan, email, password, refresh)
            label = PLANS[plan].name
            print(f"\n[{label}] {tenant.name}: {created} produtos novos, {photos} fotos")
            print(f"  Cardápio: {settings.tenant_url(slug, '/')}")
            print(f"  Painel:   {settings.tenant_url(slug, '/login')}  ({email} / {password})")

    print("Cupom DEMO10 (10%) vale nas contas com plano pago.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
