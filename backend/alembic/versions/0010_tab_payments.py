"""tab payments (PIX per person) and the city printed in PIX codes

Revision ID: 0010
Revises: 0009
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0010"
down_revision: Union[str, Sequence[str], None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_PAYMENT = sa.Enum("PIX", "CARD", "CASH", "TAB", name="paymentmethod", native_enum=False, length=20)


def upgrade() -> None:
    op.add_column("tenants", sa.Column("city", sa.String(60), nullable=True))
    op.create_table(
        "tab_payments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tab_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("method", _PAYMENT, nullable=False),
        sa.Column("status", sa.Enum("REPORTED", "CONFIRMED", "REJECTED", name="tabpaymentstatus", native_enum=False, length=20), nullable=False),
        sa.Column("payer_name", sa.String(120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("amount > 0", name="chk_tab_payments_amount"),
        sa.ForeignKeyConstraint(["tenant_id", "tab_id"], ["tabs.tenant_id", "tabs.id"], name="fk_tab_payments_tenant_tab", ondelete="CASCADE"),
    )
    op.create_index("idx_tab_payments_tab", "tab_payments", ["tab_id"])
    op.execute("ALTER TABLE tab_payments ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.drop_index("idx_tab_payments_tab", table_name="tab_payments")
    op.drop_table("tab_payments")
    op.drop_column("tenants", "city")
