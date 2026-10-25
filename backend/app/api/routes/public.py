"""Endpoints used by the customer-facing menu (no authentication, scoped by the X-Tenant header)."""
import time
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services import loyalty, push
from app.core.exceptions import BusinessRuleError, NotFoundError
from app.core.rate_limit import coupon_check_rate_limit, public_lookup_rate_limit, public_order_rate_limit
from app.core.tenancy import get_tenant
from app.models.order import Order, OrderStatus
from app.models.order_review import OrderReview
from app.models.push_subscription import OrderPushSubscription
from app.models.tenant import Tenant
from app.repositories.category import CategoryRepository
from app.repositories.customer import CustomerRepository
from app.repositories.order import OrderRepository
from app.repositories.product import ProductRepository
from app.schemas.order import OrderCreate, OrderItemCreate
from app.schemas.public import (
    OrderPushIn,
    ReviewCreate,
    CouponCheckRequest,
    CouponCheckResponse,
    PublicCategory,
    PublicHistoryItem,
    PublicMenu,
    PublicOrderCreate,
    PublicOrderResponse,
    PublicOrderTracking,
    PublicProduct,
)
from app.core.plans import public_tenant
from app.core.tables import normalize_table_label, valid_table_code
from app.schemas.tab import PixCode, PixReport, PublicTab, ServiceFeeChoice, TabCloseRequest, WaiterCall
from app.services.access_log import record_access
from app.services.coupon import CouponService
from app.services.tab import TabService
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
        categories=[PublicCategory(id=c.id, name=c.name, image_url=c.image_url,
                                   available_from=c.available_from.strftime("%H:%M") if c.available_from else None,
                                   available_until=c.available_until.strftime("%H:%M") if c.available_until else None)
                    for c in categories],
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


@router.post("/coupons/check", response_model=CouponCheckResponse, dependencies=[Depends(coupon_check_rate_limit)])
def check_coupon(data: CouponCheckRequest, tenant: Tenant = Depends(get_tenant), db: Session = Depends(get_db)):
    coupon, discount = CouponService(db, tenant.id).validate(data.code, data.subtotal)
    return CouponCheckResponse(code=coupon.code, discount=discount)


@router.post(
    "/orders",
    response_model=PublicOrderResponse,
    status_code=201,
    dependencies=[Depends(public_order_rate_limit)],
)
def create_public_order(
    data: PublicOrderCreate, request: Request, background: BackgroundTasks, tenant: Tenant = Depends(get_tenant), db: Session = Depends(get_db),
):
    customer = CustomerRepository(db, tenant.id).get_or_create_by_phone(data.customer_name, data.customer_phone)
    if data.marketing_opt_in and not customer.marketing_opt_in:
        customer.marketing_opt_in, customer.marketing_opt_in_at = True, datetime.now(timezone.utc)
    order = OrderService(db, tenant.id).create(
        OrderCreate(
            customer_id=customer.id,
            payment_method=data.payment_method,
            service_type=data.service_type,
            table_label=data.table_label,
            table_code=data.table_code,
            delivery_address=data.delivery_address,
            notes=data.notes,
            coupon_code=data.coupon_code,
            waive_service_fee=data.waive_service_fee,
            delivery_zone=data.delivery_zone,
            scheduled_for=data.scheduled_for,
            notify_whatsapp=data.notify_whatsapp,
            items=[
                OrderItemCreate(product_id=i.product_id, quantity=i.quantity, notes=i.notes, options=i.options)
                for i in data.items
            ],
        ),
        public=True,
    )
    record_access(db, request, "ORDER", tenant.id, reference=f"#{order.order_number}")
    where = f"Mesa {order.table_label}" if order.table_label else {"TAKEAWAY": "Retirada", "DELIVERY": "Entrega"}.get(order.service_type.value, "")
    background.add_task(push.notify_tenant, tenant.id, f"Novo pedido #{order.order_number}", f"{where} · {customer.name} · R$ {order.total:.2f}".replace(".", ","))
    return PublicOrderResponse(
        order_number=order.order_number,
        status=order.status.value,
        total=str(order.total),
        public_token=order.public_token,
        payment_status=order.payment_status.value,
        tab_token=order.tab.public_token if order.tab_id else None,
    )


@router.get("/tables/{table_label}/tab", response_model=PublicTab, dependencies=[Depends(public_lookup_rate_limit)])
def table_tab(
    table_label: str,
    k: str | None = Query(default=None, max_length=20),
    tenant: Tenant = Depends(get_tenant),
    db: Session = Depends(get_db),
):
    """The bill already open at this table, so a second phone scanning the QR Code joins it.
    Requires the code printed in that table's QR Code (`k`), so a table number alone reveals nothing."""
    label = normalize_table_label(table_label)
    tab = TabService(db, tenant.id).active_for_table(label) if valid_table_code(tenant.table_secret, label, k) else None
    if tab is None:
        raise NotFoundError("Nenhuma comanda aberta nesta mesa.")
    return TabService(db, tenant.id).to_public(tab)


@router.get("/tabs/{token}", response_model=PublicTab, dependencies=[Depends(public_lookup_rate_limit)])
def public_tab(token: UUID, tenant: Tenant = Depends(get_tenant), db: Session = Depends(get_db)):
    service = TabService(db, tenant.id)
    return service.to_public(service.get_by_token(token))


@router.post("/tabs/{token}/close-request", response_model=PublicTab, dependencies=[Depends(public_order_rate_limit)])
def request_tab_close(token: UUID, data: TabCloseRequest, tenant: Tenant = Depends(get_tenant), db: Session = Depends(get_db)):
    """The customer asks for the bill: the table lights up on the staff's Mesas screen."""
    service = TabService(db, tenant.id)
    return service.to_public(service.request_close(token, tenant, data.payment_method, data.split_count))


WAITER_REASONS = {"GARCOM": "chamou o garçom", "CONTA": "pediu a conta", "GUARDANAPO": "pediu guardanapo", "TALHERES": "pediu talheres", "OUTRO": "precisa de ajuda"}


@router.post("/tabs/{token}/call", response_model=PublicTab, dependencies=[Depends(public_order_rate_limit)])
def call_waiter(token: UUID, data: WaiterCall, background: BackgroundTasks, tenant: Tenant = Depends(get_tenant), db: Session = Depends(get_db)):
    """"Chamar garçom" from the table: alerts the floor (Mesas screen, sound and staff phones)."""
    service = TabService(db, tenant.id)
    tab = service.call_waiter(service.get_by_token(token), data.reason)
    background.add_task(push.notify_tenant, tenant.id, f"Mesa {tab.table_label} {WAITER_REASONS[data.reason]}", "Toque para ver as mesas", "/painel/mesas")
    return service.to_public(tab)


@router.post("/tabs/{token}/service-fee", response_model=PublicTab, dependencies=[Depends(public_order_rate_limit)])
def tab_service_fee(token: UUID, data: ServiceFeeChoice, tenant: Tenant = Depends(get_tenant), db: Session = Depends(get_db)):
    """The service fee is optional (tip): the table can take it out of the bill, or put it back."""
    service = TabService(db, tenant.id)
    return service.to_public(service.set_service_fee(service.get_by_token(token), tenant, data.waived))


@router.get("/tabs/{token}/pix", response_model=PixCode, dependencies=[Depends(public_lookup_rate_limit)])
def tab_pix_code(
    token: UUID,
    amount: Decimal | None = Query(default=None, gt=0, max_digits=10, decimal_places=2),
    tenant: Tenant = Depends(get_tenant),
    db: Session = Depends(get_db),
):
    """PIX copia e cola for the bill (or one person's share), paid straight to the restaurant's PIX key."""
    return TabService(db, tenant.id).pix_code(token, tenant, amount)


@router.post("/tabs/{token}/pix-report", response_model=PublicTab, dependencies=[Depends(public_order_rate_limit)])
def report_tab_pix(token: UUID, data: PixReport, tenant: Tenant = Depends(get_tenant), db: Session = Depends(get_db)):
    """"Já paguei": the waiter gets an alert to check the bank and confirm."""
    service = TabService(db, tenant.id)
    return service.to_public(service.report_pix(token, tenant, data.amount, data.payer_name))


@router.post("/orders/{public_token}/cancel", status_code=204, dependencies=[Depends(public_order_rate_limit)])
def cancel_public_order(public_token: UUID, tenant: Tenant = Depends(get_tenant), db: Session = Depends(get_db)):
    OrderService(db, tenant.id).cancel_by_customer(public_token)


@router.post("/orders/{public_token}/push", status_code=204, dependencies=[Depends(public_order_rate_limit)])
def subscribe_order_push(public_token: UUID, data: OrderPushIn, tenant: Tenant = Depends(get_tenant), db: Session = Depends(get_db)):
    """The customer wants a notification on this phone when the order is being prepared / is ready."""
    order = OrderRepository(db, tenant.id).get_by_public_token(public_token)
    if order is None:
        raise NotFoundError("Pedido não encontrado.")
    if not data.endpoint.startswith("https://"):
        raise BusinessRuleError("Inscrição inválida.")
    exists = db.scalar(select(OrderPushSubscription).where(OrderPushSubscription.order_id == order.id, OrderPushSubscription.endpoint == data.endpoint))
    if exists is None:
        db.add(OrderPushSubscription(order_id=order.id, endpoint=data.endpoint, p256dh=data.keys.p256dh, auth=data.keys.auth))
        db.commit()


@router.get("/orders/{public_token}/pix", response_model=PixCode, dependencies=[Depends(public_lookup_rate_limit)])
def order_pix_code(public_token: UUID, tenant: Tenant = Depends(get_tenant), db: Session = Depends(get_db)):
    """QR Code / copia e cola with the order's exact total (pickup and delivery orders paid by PIX)."""
    return OrderService(db, tenant.id).pix_code(public_token, tenant)


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
        scheduled_for=order.scheduled_for,
        history=[{"status": h.status.value, "at": h.created_at} for h in order.status_history],
        prep_minutes=tenant.prep_minutes,
        loyalty=(card.model_dump() if (card := loyalty.card(db, tenant, order.customer)) else None),
        review_stars=review.stars if (review := db.scalar(select(OrderReview).where(OrderReview.order_id == order.id))) else None,
        google_review_url=tenant.google_review_url,
    )


@router.post("/orders/{public_token}/review", status_code=201, dependencies=[Depends(public_order_rate_limit)])
def review_order(public_token: UUID, data: ReviewCreate, tenant: Tenant = Depends(get_tenant), db: Session = Depends(get_db)):
    """1-5 stars after delivery, once per order."""
    order = OrderRepository(db, tenant.id).get_by_public_token(public_token)
    if order is None:
        raise NotFoundError("Pedido não encontrado.")
    if order.status is not OrderStatus.FINISHED:
        raise BusinessRuleError("Você pode avaliar depois que o pedido for entregue.")
    if db.scalar(select(OrderReview).where(OrderReview.order_id == order.id)):
        raise BusinessRuleError("Este pedido já foi avaliado. Obrigado!")
    db.add(OrderReview(tenant_id=tenant.id, order_id=order.id, stars=data.stars, comment=(data.comment or "").strip() or None))
    db.commit()
    return {"google_review_url": tenant.google_review_url if data.stars == 5 else None}
