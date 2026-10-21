"""tabs (comanda por mesa): open bill per table, paid at the end

Revision ID: 0004
Revises: 0003
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: Union[str, Sequence[str], None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_PAYMENT = sa.Enum("PIX", "CARD", "CASH", "TAB", name="paymentmethod", native_enum=False, length=20)


def upgrade() -> None:
    op.create_table(
        "tabs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("public_token", postgresql.UUID(as_uuid=True), nullable=False, unique=True),
        sa.Column("table_label", sa.String(30), nullable=False),
        sa.Column("status", sa.Enum("PENDING", "OPEN", "CLOSING", "CLOSED", "CANCELLED", name="tabstatus", native_enum=False, length=20), nullable=False),
        sa.Column("opened_by", sa.String(120), nullable=True),
        sa.Column("requested_payment_method", _PAYMENT, nullable=True),
        sa.Column("split_count", sa.SmallInteger(), nullable=True),
        sa.Column("payment_method", _PAYMENT, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_order_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("close_requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("tenant_id", "id", name="uq_tabs_tenant_id"),
        sa.UniqueConstraint("tenant_id", "number", name="uq_tabs_tenant_number"),
    )
    op.create_index(
        "uq_tabs_active_table", "tabs", ["tenant_id", "table_label"], unique=True,
        postgresql_where=sa.text("status IN ('PENDING', 'OPEN', 'CLOSING')"),
    )
    op.create_index("idx_tabs_tenant_status", "tabs", ["tenant_id", "status"])

    op.add_column("orders", sa.Column("tab_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key("fk_orders_tenant_tab", "orders", "tabs", ["tenant_id", "tab_id"], ["tenant_id", "id"])
    op.create_index("idx_orders_tab_id", "orders", ["tab_id"])

    op.add_column("tenants", sa.Column("tabs_enabled", sa.Boolean(), server_default="false", nullable=False))
    op.add_column("tenants", sa.Column("tabs_auto_approve", sa.Boolean(), server_default="false", nullable=False))
    op.add_column("tenants", sa.Column("tab_idle_minutes", sa.Integer(), server_default="20", nullable=False))
    op.add_column("tenants", sa.Column("tab_counter", sa.BigInteger(), server_default="0", nullable=False))


def downgrade() -> None:
    for column in ("tab_counter", "tab_idle_minutes", "tabs_auto_approve", "tabs_enabled"):
        op.drop_column("tenants", column)
    op.drop_index("idx_orders_tab_id", table_name="orders")
    op.drop_constraint("fk_orders_tenant_tab", "orders", type_="foreignkey")
    op.drop_column("orders", "tab_id")
    op.drop_index("idx_tabs_tenant_status", table_name="tabs")
    op.drop_index("uq_tabs_active_table", table_name="tabs")
    op.drop_table("tabs")
