"""Open bills per table (comanda): dine-in orders pile up on the table's tab and are paid once, at the end."""
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import BusinessRuleError, NotFoundError
from app.models.order import Order, OrderStatus, PaymentMethod, PaymentStatus
from app.models.order_status_history import OrderStatusHistory
from app.core.pix import brcode, normalize_pix_key
from app.models.tab import ACTIVE_TAB_STATUSES, Tab, TabStatus
from app.models.tab_payment import TabPayment, TabPaymentStatus
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.tab import PixCode, PublicTab, TabAlerts, TabOrder, TabOrderItem, TabPaymentOut, TabResponse, TabTotals
from app.services.audit import record_audit
from app.services.coupon import CouponService

LATE_ORDER_MINUTES = 20
_CENTS = Decimal("0.01")
_COOKING = (OrderStatus.RECEIVED, OrderStatus.PREPARING)
_LOAD = (
    selectinload(Tab.orders).selectinload(Order.items),
    selectinload(Tab.orders).selectinload(Order.customer),
    selectinload(Tab.payments),
)


def _minutes_since(moment: datetime | None, now: datetime) -> int | None:
    return None if moment is None else max(0, int((now - moment).total_seconds() // 60))


class TabService:
    def __init__(self, db: Session, tenant_id: UUID):
        self.db = db
        self.tenant_id = tenant_id

    # ---- lookups ------------------------------------------------------------------------------
    def _query(self):
        return select(Tab).options(*_LOAD).where(Tab.tenant_id == self.tenant_id)

    def get(self, tab_id: UUID) -> Tab:
        tab = self.db.scalar(self._query().where(Tab.id == tab_id))
        if tab is None:
            raise NotFoundError("Comanda não encontrada.")
        return tab

    def get_by_token(self, token: UUID) -> Tab:
        tab = self.db.scalar(self._query().where(Tab.public_token == token))
        if tab is None:
            raise NotFoundError("Comanda não encontrada.")
        return tab

    def active_for_table(self, table_label: str) -> Tab | None:
        return self.db.scalar(
            self._query().where(Tab.table_label == table_label, Tab.status.in_(ACTIVE_TAB_STATUSES))
        )

    def list_active(self) -> list[Tab]:
        return list(self.db.scalars(
            self._query().where(Tab.status.in_(ACTIVE_TAB_STATUSES)).order_by(Tab.created_at)
        ).all())

    # ---- ordering -----------------------------------------------------------------------------
    def attach(self, tenant: Tenant, table_label: str, opened_by: str | None, by_staff: bool) -> Tab:
        """The table's active tab for a new order, opening one if needed. Called inside the order's transaction."""
        now = datetime.now(timezone.utc)
        tab = self.db.scalar(
            select(Tab).where(
                Tab.tenant_id == self.tenant_id, Tab.table_label == table_label, Tab.status.in_(ACTIVE_TAB_STATUSES)
            ).with_for_update()
        )
        if tab is None:
            approved = by_staff or tenant.tabs_auto_approve
            tab = Tab(
                tenant_id=self.tenant_id,
                number=self._next_number(),
                table_label=table_label,
                opened_by=opened_by,
                status=TabStatus.OPEN if approved else TabStatus.PENDING,
                approved_at=now if approved else None,
            )
            try:
                with self.db.begin_nested():
                    self.db.add(tab)
            except IntegrityError:
                # Another phone at the same table opened it a moment ago: join that one.
                tab = self.db.scalar(
                    select(Tab).where(
                        Tab.tenant_id == self.tenant_id, Tab.table_label == table_label, Tab.status.in_(ACTIVE_TAB_STATUSES)
                    ).with_for_update()
                )
        elif tab.status is TabStatus.CLOSING:
            # Automation: ordering again after asking for the bill reopens it.
            tab.status, tab.close_requested_at, tab.requested_payment_method, tab.split_count = TabStatus.OPEN, None, None, None
        tab.last_order_at = now
        return tab

    def _next_number(self) -> int:
        return int(self.db.execute(
            update(Tenant).where(Tenant.id == self.tenant_id)
            .values(tab_counter=Tenant.tab_counter + 1).returning(Tenant.tab_counter)
        ).scalar_one())

    # ---- staff actions ------------------------------------------------------------------------
    def approve(self, tab_id: UUID, actor: User) -> Tab:
        tab = self.get(tab_id)
        if tab.status is not TabStatus.PENDING:
            raise BusinessRuleError("Esta mesa já foi aprovada.")
        tab.status, tab.approved_at = TabStatus.OPEN, datetime.now(timezone.utc)
        record_audit(self.db, self.tenant_id, actor, "TAB_APPROVED", "TAB", tab.id, f"mesa {tab.table_label}")
        self.db.commit()
        return tab

    def cancel(self, tab_id: UUID, reason: str, actor: User) -> Tab:
        """Rejects a pending table or cancels an open bill; its orders are cancelled too."""
        tab = self.get(tab_id)
        if tab.status not in ACTIVE_TAB_STATUSES:
            raise BusinessRuleError("Esta comanda já foi encerrada.")
        coupons = CouponService(self.db, self.tenant_id)
        for order in tab.orders:
            if order.status in (OrderStatus.FINISHED, OrderStatus.CANCELLED):
                continue
            order.status = OrderStatus.CANCELLED
            order.status_history.append(OrderStatusHistory(status=OrderStatus.CANCELLED, reason=reason, changed_by_user_id=actor.id))
            coupons.release(order.coupon_code)
        tab.status, tab.closed_at = TabStatus.CANCELLED, datetime.now(timezone.utc)
        record_audit(self.db, self.tenant_id, actor, "TAB_CANCELLED", "TAB", tab.id, f"mesa {tab.table_label}: {reason}")
        self.db.commit()
        return tab

    def cancel_if_empty(self, tab_id: UUID, actor: User | None) -> None:
        """Automation: when every order of a bill was cancelled, the bill closes itself (the caller commits)."""
        tab = self.db.get(Tab, tab_id)
        if tab is None or tab.status not in ACTIVE_TAB_STATUSES:
            return
        self.db.flush()
        if all(order.status is OrderStatus.CANCELLED for order in tab.orders):
            tab.status, tab.closed_at = TabStatus.CANCELLED, datetime.now(timezone.utc)
            record_audit(self.db, self.tenant_id, actor, "TAB_CANCELLED", "TAB", tab.id, f"mesa {tab.table_label}: todos os pedidos cancelados")

    def close(self, tab_id: UUID, payment_method: PaymentMethod, actor: User) -> Tab:
        """Payment received: whatever is still open is paid with `payment_method`, every order is marked paid,
        served ones are finished and the table is free again."""
        tab = self.get(tab_id)
        if tab.status not in (TabStatus.OPEN, TabStatus.CLOSING):
            raise BusinessRuleError("Só é possível fechar uma comanda aberta.")
        if not any(order.status is not OrderStatus.CANCELLED for order in tab.orders):
            raise BusinessRuleError("Não há nada para cobrar nesta mesa. Cancele a comanda em vez de fechar.")
        cooking = sum(1 for order in tab.orders if order.status in _COOKING)
        if cooking:
            raise BusinessRuleError(f"Há {cooking} pedido(s) ainda na cozinha. Entregue ou cancele antes de fechar a conta.")
        remaining = self.totals(tab).remaining
        if remaining > 0:
            self._add_payment(tab, remaining, payment_method, TabPaymentStatus.CONFIRMED, None)
        self._finalize(tab, payment_method, actor)
        self.db.commit()
        return tab

    def _finalize(self, tab: Tab, payment_method: PaymentMethod, actor: User | None) -> None:
        now = datetime.now(timezone.utc)
        # Reported PIX that nobody confirmed are dropped: the bill was settled another way.
        for payment in tab.payments:
            if payment.status is TabPaymentStatus.REPORTED:
                payment.status, payment.resolved_at = TabPaymentStatus.REJECTED, now
        for order in tab.orders:
            if order.status is OrderStatus.CANCELLED:
                continue
            order.payment_method, order.payment_status, order.paid_at = payment_method, PaymentStatus.PAID, now
            if order.status is not OrderStatus.FINISHED:
                order.status = OrderStatus.FINISHED
                order.status_history.append(OrderStatusHistory(status=OrderStatus.FINISHED, changed_by_user_id=actor.id))
        tab.status, tab.payment_method, tab.closed_at = TabStatus.CLOSED, payment_method, now
        record_audit(
            self.db, self.tenant_id, actor, "TAB_CLOSED", "TAB", tab.id,
            f"mesa {tab.table_label} total={self.totals(tab).total} method={payment_method.value}",
        )

    # ---- payments (whole bill or one person's share) ----------------------------------------
    def _add_payment(self, tab: Tab, amount: Decimal, method: PaymentMethod, status: TabPaymentStatus, payer: str | None) -> TabPayment:
        payment = TabPayment(
            tenant_id=self.tenant_id, tab_id=tab.id, amount=amount.quantize(_CENTS), method=method, status=status,
            payer_name=payer, resolved_at=datetime.now(timezone.utc) if status is TabPaymentStatus.CONFIRMED else None,
        )
        self.db.add(payment)
        self.db.flush()
        self.db.refresh(tab, ["payments"])
        return payment

    def _settle_if_paid(self, tab: Tab, actor: User | None) -> None:
        """Automation: a bill fully paid closes itself (when nothing is still being cooked)."""
        totals = self.totals(tab)
        if totals.remaining > 0 or any(order.status in _COOKING for order in tab.orders):
            return
        confirmed = [p for p in tab.payments if p.status is TabPaymentStatus.CONFIRMED]
        main_method = max(confirmed, key=lambda p: p.amount).method if confirmed else PaymentMethod.CASH
        self._finalize(tab, main_method, actor)

    def pix_code(self, token: UUID, tenant: Tenant, amount: Decimal | None) -> PixCode:
        tab = self.get_by_token(token)
        if tab.status not in (TabStatus.OPEN, TabStatus.CLOSING):
            raise BusinessRuleError("Esta comanda não está aberta para pagamento.")
        key = normalize_pix_key(tenant.pix_key or "")
        if not key or "PIX" not in tenant.accepted_payments:
            raise BusinessRuleError("Este estabelecimento não recebe PIX pelo cardápio. Peça a conta ao garçom.")
        remaining = self.totals(tab).remaining
        value = (amount or remaining).quantize(_CENTS)
        if value <= 0 or value > remaining:
            raise BusinessRuleError(f"Informe um valor entre R$ 0,01 e R$ {remaining:.2f}.".replace(".", ","))
        code = brcode(key, value, tenant.name, tenant.city or "BRASIL", f"MESA{tab.table_label}")
        return PixCode(code=code, amount=value)

    def report_pix(self, token: UUID, tenant: Tenant, amount: Decimal, payer: str | None) -> Tab:
        """The customer says the PIX was sent; staff gets a "check the bank" alert to confirm."""
        tab = self.get_by_token(token)
        if tab.status not in (TabStatus.OPEN, TabStatus.CLOSING):
            raise BusinessRuleError("Esta comanda não está aberta para pagamento.")
        if amount > self.totals(tab).remaining:
            raise BusinessRuleError("Este valor é maior que o saldo da conta.")
        self._add_payment(tab, amount, PaymentMethod.PIX, TabPaymentStatus.REPORTED, payer)
        if tab.status is TabStatus.OPEN:
            tab.status, tab.close_requested_at, tab.requested_payment_method = TabStatus.CLOSING, datetime.now(timezone.utc), PaymentMethod.PIX
        self.db.commit()
        return tab

    def add_payment(self, tab_id: UUID, amount: Decimal, method: PaymentMethod, actor: User) -> Tab:
        tab = self.get(tab_id)
        if tab.status not in (TabStatus.OPEN, TabStatus.CLOSING):
            raise BusinessRuleError("Esta comanda não está aberta.")
        if amount > self.totals(tab).remaining:
            raise BusinessRuleError("Este valor é maior que o saldo da conta.")
        self._add_payment(tab, amount, method, TabPaymentStatus.CONFIRMED, None)
        record_audit(self.db, self.tenant_id, actor, "TAB_PAYMENT", "TAB", tab.id, f"mesa {tab.table_label} {method.value} {amount}")
        self._settle_if_paid(tab, actor)
        self.db.commit()
        return tab

    def resolve_payment(self, tab_id: UUID, payment_id: UUID, confirm: bool, actor: User) -> Tab:
        tab = self.get(tab_id)
        payment = next((p for p in tab.payments if p.id == payment_id), None)
        if payment is None or payment.status is not TabPaymentStatus.REPORTED:
            raise BusinessRuleError("Este pagamento já foi resolvido.")
        if confirm and payment.amount > self.totals(tab).remaining:
            raise BusinessRuleError("Este valor é maior que o saldo da conta.")
        payment.status = TabPaymentStatus.CONFIRMED if confirm else TabPaymentStatus.REJECTED
        payment.resolved_at = datetime.now(timezone.utc)
        record_audit(
            self.db, self.tenant_id, actor, "TAB_PAYMENT_CONFIRMED" if confirm else "TAB_PAYMENT_REJECTED", "TAB", tab.id,
            f"mesa {tab.table_label} PIX {payment.amount}",
        )
        self.db.flush()
        if confirm:
            self._settle_if_paid(tab, actor)
        self.db.commit()
        return tab

    # ---- customer actions ---------------------------------------------------------------------
    def request_close(self, token: UUID, tenant: Tenant, payment_method: PaymentMethod, split_count: int | None) -> Tab:
        tab = self.get_by_token(token)
        if tab.status not in (TabStatus.OPEN, TabStatus.CLOSING):
            raise BusinessRuleError("Esta comanda não está aberta.")
        if payment_method.value not in tenant.accepted_payments:
            raise BusinessRuleError("Esta forma de pagamento não está disponível.")
        if not any(order.status is not OrderStatus.CANCELLED for order in tab.orders):
            raise BusinessRuleError("Ainda não há nada para pagar nesta mesa.")
        tab.status, tab.close_requested_at = TabStatus.CLOSING, datetime.now(timezone.utc)
        tab.requested_payment_method, tab.split_count = payment_method, split_count
        self.db.commit()
        return tab

    # ---- views --------------------------------------------------------------------------------
    @staticmethod
    def totals(tab: Tab) -> TabTotals:
        live = [order for order in tab.orders if order.status is not OrderStatus.CANCELLED]
        total = sum((order.total for order in live), Decimal("0.00"))
        per_person = (total / tab.split_count).quantize(_CENTS, rounding=ROUND_HALF_UP) if tab.split_count and tab.split_count > 1 else None
        paid = sum((p.amount for p in tab.payments if p.status is TabPaymentStatus.CONFIRMED), Decimal("0.00"))
        reported = sum((p.amount for p in tab.payments if p.status is TabPaymentStatus.REPORTED), Decimal("0.00"))
        return TabTotals(
            subtotal=sum((order.subtotal for order in live), Decimal("0.00")),
            discount=sum((order.discount for order in live), Decimal("0.00")),
            service_fee=sum((order.service_fee for order in live), Decimal("0.00")),
            total=total,
            per_person=per_person,
            paid=paid,
            reported=reported,
            remaining=max(total - paid, Decimal("0.00")),
        )

    @staticmethod
    def _payments(tab: Tab) -> list[TabPaymentOut]:
        return [
            TabPaymentOut(id=p.id, amount=p.amount, method=p.method, status=p.status.value, payer_name=p.payer_name, created_at=p.created_at)
            for p in tab.payments
        ]

    @staticmethod
    def _orders(tab: Tab) -> list[TabOrder]:
        return [
            TabOrder(
                id=order.id, order_number=order.order_number, status=order.status.value, customer_name=order.customer_name,
                total=order.total, created_at=order.created_at,
                items=[
                    TabOrderItem(product_id=i.product_id, product_name=i.product_name, quantity=i.quantity, options=i.options or [], notes=i.notes)
                    for i in order.items
                ],
            )
            for order in tab.orders
        ]

    @staticmethod
    def alerts(tab: Tab, tenant: Tenant, now: datetime | None = None) -> TabAlerts:
        now = now or datetime.now(timezone.utc)
        cooking = [order for order in tab.orders if order.status in _COOKING]
        since_last = _minutes_since(tab.last_order_at, now)
        return TabAlerts(
            needs_approval=tab.status is TabStatus.PENDING,
            wants_to_close=tab.status is TabStatus.CLOSING,
            idle=(
                tab.status is TabStatus.OPEN and not cooking
                and since_last is not None and since_last >= tenant.tab_idle_minutes
            ),
            late_orders=sum(1 for order in cooking if _minutes_since(order.created_at, now) >= LATE_ORDER_MINUTES),
            payments_to_confirm=sum(1 for p in tab.payments if p.status is TabPaymentStatus.REPORTED),
            minutes_open=_minutes_since(tab.created_at, now) or 0,
            minutes_since_last_order=since_last,
        )

    def to_response(self, tab: Tab, tenant: Tenant) -> TabResponse:
        return TabResponse(
            id=tab.id, number=tab.number, public_token=tab.public_token, table_label=tab.table_label, status=tab.status,
            opened_by=tab.opened_by, requested_payment_method=tab.requested_payment_method, split_count=tab.split_count,
            payment_method=tab.payment_method, created_at=tab.created_at, last_order_at=tab.last_order_at,
            close_requested_at=tab.close_requested_at, closed_at=tab.closed_at,
            totals=self.totals(tab), orders=self._orders(tab), payments=self._payments(tab), alerts=self.alerts(tab, tenant),
        )

    def to_public(self, tab: Tab) -> PublicTab:
        return PublicTab(
            number=tab.number, public_token=tab.public_token, table_label=tab.table_label, status=tab.status,
            requested_payment_method=tab.requested_payment_method, split_count=tab.split_count,
            last_order_at=tab.last_order_at, totals=self.totals(tab), orders=self._orders(tab), payments=self._payments(tab),
        )
