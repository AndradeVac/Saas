"""Digital loyalty card: every `goal` delivered orders of the same phone earn the reward. No app, no paper card."""
from __future__ import annotations

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessRuleError
from app.core.plans import LOYALTY, has_feature
from app.models.customer import Customer
from app.models.order import Order, OrderStatus
from app.models.tenant import Tenant


class LoyaltyCard(BaseModel):
    stamps: int  # stamps on the current card (0..goal)
    goal: int
    reward: str
    rewards_available: int  # full cards not redeemed yet


def active(tenant: Tenant) -> bool:
    return tenant.loyalty_enabled and bool(tenant.loyalty_reward) and has_feature(tenant, LOYALTY)


def card(db: Session, tenant: Tenant, customer: Customer) -> LoyaltyCard | None:
    if not active(tenant):
        return None
    delivered = int(db.scalar(
        select(func.count(Order.id)).where(Order.tenant_id == tenant.id, Order.customer_id == customer.id, Order.status == OrderStatus.FINISHED)
    ) or 0)
    goal = max(tenant.loyalty_goal, 1)
    progress = max(delivered - customer.loyalty_redemptions * goal, 0)
    return LoyaltyCard(stamps=progress % goal if progress < goal else goal, goal=goal, reward=tenant.loyalty_reward or "",
                       rewards_available=progress // goal)


def redeem(db: Session, tenant: Tenant, customer: Customer) -> LoyaltyCard:
    current = card(db, tenant, customer)
    if current is None:
        raise BusinessRuleError("O cartão fidelidade não está ativo.")
    if current.rewards_available < 1:
        raise BusinessRuleError(f"Faltam {current.goal - current.stamps} pedidos para este cliente ganhar o prêmio.")
    customer.loyalty_redemptions += 1
    db.commit()
    return card(db, tenant, customer)  # type: ignore[return-value]
