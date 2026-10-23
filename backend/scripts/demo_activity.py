"""Fill a DEMO account with weeks of realistic sales, so dashboards, reports and the history look like a
restaurant in operation (for showing the product to prospects).

Usage (from backend/):
    python -m scripts.demo_activity hamburgueria-teste --days 60 --confirm hamburgueria-teste
    python -m scripts.demo_activity hamburgueria-teste --lapsed-only 12 --confirm hamburgueria-teste

What it creates, in the tenant's own time zone: lunch and dinner peaks, busier Fridays and Saturdays, closed on
Mondays, returning customers, dine-in / takeaway / delivery, PIX / card / cash, some coupons and ~4% cancellations.
Prices, options, service fee and delivery fee are computed exactly like a real order.
Only ever run it on a demo account: the orders are fake. `--confirm` must repeat the slug.
"""
from __future__ import annotations

import argparse
import random
import sys
from datetime import date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.phone import phone_digits
from app.models.coupon import Coupon, CouponKind
from app.models.customer import Customer
from app.models.order import Order, OrderStatus, PaymentMethod, PaymentStatus, ServiceType
from app.models.order_item import OrderItem
from app.models.order_status_history import OrderStatusHistory
from app.models.product import Product
from app.models.tenant import Tenant
from app.repositories.tenant import TenantRepository

CENTS = Decimal("0.01")
FIRST = ["Ana", "Bruno", "Carla", "Diego", "Eduarda", "Felipe", "Gabriela", "Henrique", "Isabela", "João", "Karina", "Lucas",
         "Mariana", "Nicolas", "Olívia", "Paulo", "Rafaela", "Samuel", "Tatiane", "Vinícius", "Beatriz", "Caio", "Débora",
         "Gustavo", "Larissa", "Marcelo", "Natália", "Pedro", "Renata", "Thiago", "Juliana", "Rodrigo", "Camila", "André"]
LAST = ["Silva", "Santos", "Oliveira", "Souza", "Lima", "Pereira", "Costa", "Ferreira", "Almeida", "Ribeiro", "Carvalho", "Gomes"]
STREETS = ["Rua Amazonas", "Av. Goiás", "Rua Manoel Coelho", "Rua Pernambuco", "Av. Presidente Kennedy", "Rua Santo Antônio"]
# Orders per hour of the day (relative weight): lunch and dinner peaks.
HOURS = {11: 3, 12: 8, 13: 7, 14: 3, 15: 1, 16: 1, 17: 2, 18: 5, 19: 9, 20: 10, 21: 8, 22: 5, 23: 2}
# Orders per weekday (Mon=0): closed on Mondays, busy weekends.
WEEKDAY = {0: 0, 1: 14, 2: 16, 3: 19, 4: 30, 5: 36, 6: 26}


def pick_options(rng: random.Random, product: Product) -> tuple[list[dict], Decimal]:
    snapshot, extra = [], Decimal("0")
    for group in product.options or []:
        active = [o for o in group["options"] if o.get("active", True)]
        if group.get("required") or group.get("min", 0) > 0:
            chosen = [rng.choice(active)]
        elif rng.random() < 0.35:
            chosen = rng.sample(active, k=min(len(active), rng.randint(1, min(2, group.get("max", 1)))))
        else:
            chosen = []
        for option in chosen:
            price = Decimal(str(option.get("price", "0")))
            extra += price
            snapshot.append({"group": group["name"], "name": option["name"], "price": str(price)})
    return snapshot, extra


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("slug")
    parser.add_argument("--days", type=int, default=60)
    parser.add_argument("--confirm", required=True, help="repeat the slug to confirm this is a demo account")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--lapsed", type=int, default=12, help="regulars who stopped coming 25-100 days ago (win-back list)")
    parser.add_argument("--lapsed-only", type=int, default=None, metavar="N", help="only add N lapsed regulars")
    args = parser.parse_args()
    if args.confirm != args.slug:
        sys.exit("--confirm precisa repetir o slug.")
    rng = random.Random(args.seed)

    with SessionLocal() as db:
        tenant = db.scalar(select(Tenant).where(Tenant.slug == args.slug))
        if tenant is None:
            sys.exit(f"Loja '{args.slug}' não encontrada.")
        zone = ZoneInfo(tenant.timezone)
        products = list(db.scalars(select(Product).where(Product.tenant_id == tenant.id, Product.active.is_(True))))
        if not products:
            sys.exit("A loja não tem produtos ativos.")
        coupons = list(db.scalars(select(Coupon).where(Coupon.tenant_id == tenant.id, Coupon.active.is_(True))))
        # Burgers and combos sell more than water: weight by price band and featured flag.
        weights = [(3 if p.featured else 1) * (2 if Decimal("20") <= p.price <= Decimal("45") else 1) for p in products]

        taken = set(db.scalars(select(Customer.phone_digits).where(Customer.tenant_id == tenant.id)))

        def new_customer() -> Customer:
            while (phone := f"119{rng.randint(10000000, 99999999)}") in taken:
                pass
            taken.add(phone)
            customer = Customer(tenant_id=tenant.id, name=f"{rng.choice(FIRST)} {rng.choice(LAST)}", phone=phone, phone_digits=phone_digits(phone))
            db.add(customer)
            return customer

        people = [new_customer() for _ in range(70 if args.lapsed_only is None else 0)]
        db.flush()
        regulars = people[:15]  # a few come back again and again

        repository = TenantRepository(db)
        now = datetime.now(zone)
        enabled = [getattr(item, "value", item) for item in tenant.enabled_services or []]

        def build_order(customer: Customer, moment: datetime) -> bool:
            """One finished (or cancelled) order priced exactly like a real one. False when it is skipped."""
            service = rng.choices([ServiceType.DINE_IN, ServiceType.TAKEAWAY, ServiceType.DELIVERY], weights=[55, 20, 25])[0]
            if service.value not in enabled:
                service = ServiceType.TAKEAWAY
            payment = rng.choices([PaymentMethod.PIX, PaymentMethod.CARD, PaymentMethod.CASH], weights=[45, 42, 13])[0]
            order = Order(tenant_id=tenant.id, customer_id=customer.id, service_type=service, payment_method=payment,
                          table_label=str(rng.randint(1, 10)) if service is ServiceType.DINE_IN else None,
                          delivery_address=f"{rng.choice(STREETS)}, {rng.randint(10, 999)}" if service is ServiceType.DELIVERY else None,
                          created_at=moment)
            subtotal = Decimal("0")
            party = rng.choices([1, 2, 3, 4], weights=[45, 35, 12, 8])[0]
            for product in rng.choices(products, weights=weights, k=party + rng.randint(0, 1)):
                options, extra = pick_options(rng, product)
                quantity = rng.choices([1, 2], weights=[85, 15])[0]
                unit = (product.price + extra).quantize(CENTS)
                total = (unit * quantity).quantize(CENTS)
                subtotal += total
                order.items.append(OrderItem(product_id=product.id, product_name=product.name, quantity=quantity,
                                             unit_price=unit, total_price=total, options=options, created_at=moment))
            if service is not ServiceType.DINE_IN and subtotal < tenant.min_order_value:
                return False

            discount = Decimal("0")
            usable = [c for c in coupons if subtotal >= c.min_order and (c.max_uses is None or c.used_count < c.max_uses)]
            if usable and rng.random() < 0.12:
                coupon = rng.choice(usable)
                discount = (subtotal * coupon.value / 100).quantize(CENTS) if coupon.kind is CouponKind.PERCENT else min(coupon.value, subtotal)
                coupon.used_count += 1
                order.coupon_code = coupon.code
            taxable = subtotal - discount
            service_fee = ((taxable * tenant.service_fee_percent / 100).quantize(CENTS, rounding=ROUND_HALF_UP)
                           if service is ServiceType.DINE_IN and tenant.service_fee_percent else Decimal("0"))
            delivery_fee = tenant.delivery_fee if service is ServiceType.DELIVERY else Decimal("0")
            order.subtotal, order.discount, order.service_fee, order.delivery_fee = subtotal, discount, service_fee, delivery_fee
            order.total = taxable + service_fee + delivery_fee

            cancelled = rng.random() < 0.04
            order.status = OrderStatus.CANCELLED if cancelled else OrderStatus.FINISHED
            order.payment_status = PaymentStatus.PENDING if cancelled else PaymentStatus.PAID
            order.paid_at = None if cancelled else moment + timedelta(minutes=rng.randint(20, 70))
            order.updated_at = moment + timedelta(minutes=rng.randint(25, 80))
            order.status_history.append(OrderStatusHistory(status=OrderStatus.RECEIVED, created_at=moment))
            if cancelled:
                order.status_history.append(OrderStatusHistory(status=OrderStatus.CANCELLED, reason=rng.choice(
                    ["Cliente desistiu", "Endereço fora da área de entrega", "Pedido duplicado"]), created_at=moment + timedelta(minutes=4)))
            else:
                ready = rng.randint(15, 30)
                done = ready + (rng.randint(18, 40) if service is ServiceType.DELIVERY else rng.randint(3, 15))
                for minutes, status in ((3, OrderStatus.PREPARING), (ready, OrderStatus.READY), (done, OrderStatus.FINISHED)):
                    order.status_history.append(OrderStatusHistory(status=status, created_at=moment + timedelta(minutes=minutes)))
            order.order_number = repository.next_order_number(tenant.id)
            db.add(order)
            return True

        def random_moment(day: date) -> datetime:
            hour = rng.choices(list(HOURS), weights=list(HOURS.values()))[0]
            return datetime.combine(day, time(hour, rng.randint(0, 59), rng.randint(0, 59)), tzinfo=zone)

        created = 0
        days = 0 if args.lapsed_only is not None else args.days
        for offset in range(days, -1, -1) if days else ():
            day: date = (now - timedelta(days=offset)).date()
            base = WEEKDAY[day.weekday()]
            if not base:
                continue
            growth = 0.75 + 0.5 * (1 - offset / max(days, 1))  # the business grows over the period
            for _ in range(max(0, int(rng.gauss(base * growth, base * 0.15)))):
                moment = random_moment(day)
                if moment > now - timedelta(minutes=50):
                    continue  # recent orders stay for the live queue
                customer = rng.choice(regulars) if rng.random() < 0.35 else rng.choice(people)
                created += build_order(customer, moment)
            db.flush()

        # Regulars who used to come and stopped: what the "customers to win back" list is for.
        for _ in range(args.lapsed if args.lapsed_only is None else args.lapsed_only):
            customer = new_customer()
            db.flush()
            last_seen = rng.randint(25, 100)
            for visit in range(rng.randint(2, 6)):
                day = (now - timedelta(days=last_seen + visit * rng.randint(5, 12))).date()
                if WEEKDAY[day.weekday()]:
                    created += build_order(customer, random_moment(day))
        db.flush()

        # Kitchen numbers follow the clock: renumber every order of the demo by time (two steps: the pair is unique).
        orders = list(db.scalars(select(Order).where(Order.tenant_id == tenant.id).order_by(Order.created_at)))
        for order in orders:
            order.order_number += 1_000_000
        db.flush()
        for number, order in enumerate(orders, start=1):
            order.order_number = number
        tenant.order_counter = len(orders)
        db.commit()
        print(f"{tenant.slug}: {created} pedidos criados, {len(people)} clientes novos (+ clientes sumidos).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
