"""Endpoints used by the customer-facing menu (no authentication, scoped by the X-Tenant header)."""
import time
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import NotFoundError
from app.core.rate_limit import public_lookup_rate_limit, public_order_rate_limit
from app.core.tenancy import get_tenant
from app.models.order import Order
from app.models.tenant import Tenant
from app.repositories.category import CategoryRepository
from app.repositories.customer import CustomerRepository
from app.repositories.order import OrderRepository
from app.repositories.product import ProductRepository
from app.schemas.order import OrderCreate, OrderItemCreate
from app.schemas.public import (
    CouponCheckRequest,
    CouponCheckResponse,
    PublicCategory,
    PublicHistoryItem,
    PublicHistoryOrder,
    PublicMenu,
    PublicOrderCreate,
    PublicOrderResponse,
    PublicOrderTracking,
    PublicProduct,
)
from app.core.plans import public_tenant
from app.services.coupon import CouponService
from app.services.order import OrderService

router = APIRouter(prefix="/public", tags=["Public customer"])


# Rendered menus kept for a few seconds per tenant: a busy restaurant's QR-code traffic then costs one
# database round trip per worker every few seconds instead of one per customer. Edits show up within the TTL.
_MENU_TTL_SECONDS = 5
_MENU_CACHE_LIMIT = 2000
_menu_cache: dict[str, tuple[float, bytes]] = {}


def _items(order: Order) -> list[PublicHistoryItem]:
    return [
        PublicHistoryItem(
            product_id=item.product_id,
            product_name=item.product_name,
            quantity=item.quantity,
            options=item.options or [],
            notes=item.notes,
        )
        for item in order.items
    ]


def _visible_options(groups: list[dict]) -> list[dict]:
    """Hides disabled options and groups left without any."""
    visible = []
    for group in groups or []:
        options = [o for o in group["options"] if o.get("active", True)]
        if options:
            visible.append({**group, "options": options})
    return visible


@router.get("/menu", response_model=PublicMenu)
def get_menu(response: Response, tenant: Tenant = Depends(get_tenant), db: Session = Depends(get_db)):
    headers = {
        # Short shared cache: the edge/browser may reuse it too, and edits still show up within seconds.
        "Cache-Control": "public, max-age=10, stale-while-revalidate=20",
        "Vary": "X-Tenant",
    }
    now = time.monotonic()
    cached = _menu_cache.get(tenant.slug)
    if cached and now - cached[0] < _MENU_TTL_SECONDS:
        return Response(content=cached[1], media_type="application/json", headers=headers)

    categories = CategoryRepository(db, tenant.id).get_all(only_active=True)
    visible_ids = {category.id for category in categories}
    products = [
        product for product in ProductRepository(db, tenant.id).get_all(only_active=True)
        if product.category_id in visible_ids
    ]
    menu = PublicMenu(
        tenant=public_tenant(db, tenant),
        categories=[PublicCategory(id=c.id, name=c.name, image_url=c.image_url) for c in categories],
        products=[
            PublicProduct(
                id=p.id,
                category_id=p.category_id,
                name=p.name,
                description=p.description,
                image_url=p.image_url,
                price=p.price,
                featured=p.featured,
                available=p.available,
                options=_visible_options(p.options),
            )
            for p in products
        ],
    )
    body = menu.model_dump_json().encode()
    if len(_menu_cache) >= _MENU_CACHE_LIMIT:
        _menu_cache.clear()
    _menu_cache[tenant.slug] = (now, body)
    return Response(content=body, media_type="application/json", headers=headers)


@router.post("/coupons/check", response_model=CouponCheckResponse, dependencies=[Depends(public_lookup_rate_limit)])
def check_coupon(data: CouponCheckRequest, tenant: Tenant = Depends(get_tenant), db: Session = Depends(get_db)):
    coupon, discount = CouponService(db, tenant.id).validate(data.code, data.subtotal)
    return CouponCheckResponse(code=coupon.code, discount=discount)


@router.post(
    "/orders",
    response_model=PublicOrderResponse,
    status_code=201,
    dependencies=[Depends(public_order_rate_limit)],
)
def create_public_order(data: PublicOrderCreate, tenant: Tenant = Depends(get_tenant), db: Session = Depends(get_db)):
    customer = CustomerRepository(db, tenant.id).get_or_create_by_phone(data.customer_name, data.customer_phone)
    order = OrderService(db, tenant.id).create(
        OrderCreate(
            customer_id=customer.id,
            payment_method=data.payment_method,
            service_type=data.service_type,
            table_label=data.table_label,
            delivery_address=data.delivery_address,
            notes=data.notes,
            coupon_code=data.coupon_code,
            items=[
                OrderItemCreate(product_id=i.product_id, quantity=i.quantity, notes=i.notes, options=i.options)
                for i in data.items
            ],
        ),
        public=True,
    )
    return PublicOrderResponse(
        order_number=order.order_number,
        status=order.status.value,
        total=str(order.total),
        public_token=order.public_token,
        payment_status=order.payment_status.value,
    )


@router.get(
    "/orders/{public_token}",
    response_model=PublicOrderTracking,
    dependencies=[Depends(public_lookup_rate_limit)],
)
def track_public_order(public_token: UUID, tenant: Tenant = Depends(get_tenant), db: Session = Depends(get_db)):
    order = OrderRepository(db, tenant.id).get_by_public_token(public_token)
    if order is None:
        raise NotFoundError("Pedido não encontrado.")
    return PublicOrderTracking(
        order_number=order.order_number,
        status=order.status.value,
        total=str(order.total),
        subtotal=str(order.subtotal),
        discount=str(order.discount),
        service_fee=str(order.service_fee),
        delivery_fee=str(order.delivery_fee),
        created_at=order.created_at,
        payment_status=order.payment_status.value,
        payment_method=order.payment_method.value,
        service_type=order.service_type.value,
        table_label=order.table_label,
        delivery_address=order.delivery_address,
        items=_items(order),
    )


@router.get(
    "/history",
    response_model=list[PublicHistoryOrder],
    dependencies=[Depends(public_lookup_rate_limit)],
)
def public_order_history(
    phone: str = Query(min_length=10, max_length=20),
    tenant: Tenant = Depends(get_tenant),
    db: Session = Depends(get_db),
):
    customer = CustomerRepository(db, tenant.id).get_by_phone(phone)
    if customer is None:
        return []
    orders = OrderRepository(db, tenant.id).get_recent_by_customer(customer.id, limit=20)
    return [
        PublicHistoryOrder(
            order_number=o.order_number, public_token=o.public_token, status=o.status.value,
            total=str(o.total), created_at=o.created_at, items=_items(o),
        )
        for o in orders
    ]
