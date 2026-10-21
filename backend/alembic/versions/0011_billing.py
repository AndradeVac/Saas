"""online subscription billing (Asaas): tenant billing fields and processed webhook events

Revision ID: 0011
Revises: 0010
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: Union[str, Sequence[str], None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("tenants", sa.Column("billing_customer_id", sa.String(40), nullable=True))
    op.add_column("tenants", sa.Column("billing_subscription_id", sa.String(40), nullable=True, unique=True))
    op.add_column("tenants", sa.Column("billing_status", sa.String(20), server_default="NONE", nullable=False))
    op.add_column("tenants", sa.Column("billing_plan", sa.String(30), nullable=True))
    op.add_column("tenants", sa.Column("paid_until", sa.Date(), nullable=True))
    op.add_column("tenants", sa.Column("past_due_since", sa.Date(), nullable=True))
    op.create_table(
        "billing_events",
        sa.Column("id", sa.String(80), primary_key=True),  # Asaas event id: makes webhook retries idempotent
        sa.Column("event", sa.String(60), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.execute("ALTER TABLE billing_events ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.drop_table("billing_events")
    for column in ("past_due_since", "paid_until", "billing_plan", "billing_status", "billing_subscription_id", "billing_customer_id"):
        op.drop_column("tenants", column)
