"""automatic customer notifications: WhatsApp (official API) and web push when the order changes

Revision ID: 0018
Revises: 0017
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0018"
down_revision: Union[str, Sequence[str], None] = "0017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("tenants", sa.Column("notify_customers", sa.Boolean(), server_default=sa.true(), nullable=False))
    op.add_column("orders", sa.Column("notify_whatsapp", sa.Boolean(), server_default=sa.false(), nullable=False))
    op.create_table(
        "order_push_subscriptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("endpoint", sa.Text(), nullable=False),
        sa.Column("p256dh", sa.String(200), nullable=False),
        sa.Column("auth", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("order_id", "endpoint", name="uq_order_push_once"),
    )
    op.execute("ALTER TABLE order_push_subscriptions ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.drop_table("order_push_subscriptions")
    op.drop_column("orders", "notify_whatsapp")
    op.drop_column("tenants", "notify_customers")
