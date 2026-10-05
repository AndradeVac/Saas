"""Platform operator tool: list tenants, suspend/reactivate them and change their plan.

Usage (from backend/):
    python -m scripts.manage_tenant list
    python -m scripts.manage_tenant suspend padaria-do-ze
    python -m scripts.manage_tenant activate padaria-do-ze --plan pro
    python -m scripts.manage_tenant extend-trial padaria-do-ze --days 7
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select

from app.core.database import SessionLocal
from app.core.plans import DEFAULT_PAID_PLAN, PLANS
from app.models.order import Order
from app.models.tenant import Tenant, TenantStatus


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list")
    for name in ("suspend", "activate", "extend-trial"):
        command = sub.add_parser(name)
        command.add_argument("slug")
        if name == "activate":
            command.add_argument("--plan", default=DEFAULT_PAID_PLAN, choices=[k for k in PLANS if k != "trial"])
        if name == "extend-trial":
            command.add_argument("--days", type=int, default=7)
    args = parser.parse_args()

    with SessionLocal() as db:
        if args.command == "list":
            rows = db.execute(
                select(Tenant, func.count(Order.id))
                .outerjoin(Order, Order.tenant_id == Tenant.id)
                .group_by(Tenant.id)
                .order_by(Tenant.created_at)
            ).all()
            for tenant, orders in rows:
                trial = tenant.trial_ends_at.strftime("%d/%m/%Y") if tenant.trial_ends_at else "-"
                print(f"{tenant.slug:30} {tenant.status.value:10} plano={tenant.plan:8} teste até {trial}  pedidos={orders}")
            return 0

        tenant = db.scalar(select(Tenant).where(Tenant.slug == args.slug))
        if tenant is None:
            sys.exit(f"Tenant '{args.slug}' não encontrado.")
        if args.command == "suspend":
            tenant.status = TenantStatus.SUSPENDED
        elif args.command == "activate":
            tenant.status = TenantStatus.ACTIVE
            tenant.plan = args.plan
        else:
            base = max(tenant.trial_ends_at or datetime.now(timezone.utc), datetime.now(timezone.utc))
            tenant.trial_ends_at = base + timedelta(days=args.days)
            tenant.status = TenantStatus.TRIAL
        db.commit()
        print(f"{tenant.slug}: {tenant.status.value} (plano {tenant.plan})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
