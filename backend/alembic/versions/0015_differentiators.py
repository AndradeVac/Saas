"""loyalty card, product cost (margin), reviews, scheduled orders and time-limited categories

Revision ID: 0015
Revises: 0014
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0015"
down_revision: Union[str, Sequence[str], None] = "0014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("tenants", sa.Column("loyalty_enabled", sa.Boolean(), server_default=sa.false(), nullable=False))
    op.add_column("tenants", sa.Column("loyalty_goal", sa.SmallInteger(), server_default="10", nullable=False))
    op.add_column("tenants", sa.Column("loyalty_reward", sa.String(120), nullable=True))
    op.add_column("tenants", sa.Column("google_review_url", sa.String(300), nullable=True))
    op.add_column("tenants", sa.Column("scheduling_enabled", sa.Boolean(), server_default=sa.false(), nullable=False))
    op.add_column("customers", sa.Column("loyalty_redemptions", sa.Integer(), server_default="0", nullable=False))
    op.add_column("products", sa.Column("cost", sa.Numeric(10, 2), nullable=True))
    op.add_column("orders", sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=True))
    op.add_column("categories", sa.Column("available_from", sa.Time(), nullable=True))
    op.add_column("categories", sa.Column("available_until", sa.Time(), nullable=True))
    op.create_table(
        "order_reviews",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("stars", sa.SmallInteger(), nullable=False),
        sa.Column("comment", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("stars BETWEEN 1 AND 5", name="chk_order_reviews_stars"),
    )
    op.create_index("idx_order_reviews_tenant_created", "order_reviews", ["tenant_id", "created_at"])
    op.execute("ALTER TABLE order_reviews ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.drop_table("order_reviews")
    op.drop_column("categories", "available_until")
    op.drop_column("categories", "available_from")
    op.drop_column("orders", "scheduled_for")
    op.drop_column("products", "cost")
    op.drop_column("customers", "loyalty_redemptions")
    for column in ("scheduling_enabled", "google_review_url", "loyalty_reward", "loyalty_goal", "loyalty_enabled"):
        op.drop_column("tenants", column)
