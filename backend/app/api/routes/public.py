"""Endpoints used by the customer-facing menu (no authentication, scoped by the X-Tenant header)."""
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import BusinessRuleError, NotFoundError
from app.core.rate_limit import public_lookup_rate_limit, public_order_rate_limit
from app.core.tenancy import get_tenant
from app.models.customer import Customer
from app.models.order import Order
from app.models.tenant import Tenant
from app.repositories.category import CategoryRepository
from app.repositories.customer import CustomerRepository
from app.repositories.order import OrderRepository
from app.repositories.product import ProductRepository
from app.schemas.order import OrderCreate, OrderItemCreate
from app.schemas.public import (
    PublicCategory,
    PublicHistoryItem,
    PublicHistoryOrder,
    PublicMenu,
    PublicOrderCreate,
    PublicOrderResponse,
    PublicOrderTracking,
    PublicProduct,
)
from app.schemas.tenant import PublicTenant
from app.services.order import OrderService

router = APIRouter(prefix="/public", tags=["Public customer"])


def _history_items(order: Order) -> list[PublicHistoryItem]:
    return [
        PublicHistoryItem(
            product_id=item.product_id,
            product_name=item.product_name,
            quantity=item.quantity,
            notes=item.notes,
        )
        for item in order.items
    ]


@router.get("/menu", response_model=PublicMenu)
def get_menu(tenant: Tenant = Depends(get_tenant), db: Session = Depends(get_db)):
    categories = CategoryRepository(db, tenant.id).get_all(only_active=True)
    visible_ids = {category.id for category in categories}
    products = [
        product for product in ProductRepository(db, tenant.id).get_all(only_active=True)
        if product.category_id in visible_ids
    ]
    return PublicMenu(
        tenant=PublicTenant.model_validate(tenant),
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
            )
            for p in products
        ],
    )


@router.post(
    "/orders",
    response_model=PublicOrderResponse,
    status_code=201,
    dependencies=[Depends(public_order_rate_limit)],
)
def create_public_order(data: PublicOrderCreate, tenant: Tenant = Depends(get_tenant), db: Session = Depends(get_db)):
    if not tenant.accepting_orders:
        raise BusinessRuleError("O estabelecimento não está aceitando pedidos no momento.")

    customers = CustomerRepository(db, tenant.id)
    customer = customers.get_by_phone(data.customer_phone)
    if customer is None:
        customer = customers.create(Customer(name=data.customer_name, phone=data.customer_phone))
    elif customer.name != data.customer_name:
        customer.name = data.customer_name

    order = OrderService(db, tenant.id).create(
        OrderCreate(
            customer_id=customer.id,
            payment_method=data.payment_method,
            service_type=data.service_type,
            table_label=data.table_label,
            notes=data.notes,
            items=[
                OrderItemCreate(product_id=item.product_id, quantity=item.quantity, notes=item.notes)
                for item in data.items
            ],
        )
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
        created_at=order.created_at,
        payment_status=order.payment_status.value,
        service_type=order.service_type.value,
        table_label=order.table_label,
        items=_history_items(order),
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
            order_number=order.order_number,
            public_token=order.public_token,
            status=order.status.value,
            total=str(order.total),
            created_at=order.created_at,
            items=_history_items(order),
        )
        for order in orders
    ]
