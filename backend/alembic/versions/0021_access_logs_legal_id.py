"""access records (Marco Civil art. 15) and the store's legal name/CNPJ on the menu (Decreto 7.962/2013)

Revision ID: 0021
Revises: 0020
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "0021"
down_revision: Union[str, Sequence[str], None] = "0020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "access_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="SET NULL"), nullable=True),
        sa.Column("user_id", UUID(as_uuid=True), nullable=True),
        sa.Column("event", sa.String(30), nullable=False),
        sa.Column("reference", sa.String(60), nullable=True),
        sa.Column("ip", sa.String(45), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_access_logs_created_at", "access_logs", ["created_at"])
    op.execute("ALTER TABLE access_logs ENABLE ROW LEVEL SECURITY")
    op.add_column("tenants", sa.Column("legal_name", sa.String(150), nullable=True))
    op.add_column("tenants", sa.Column("legal_document", sa.String(20), nullable=True))


def downgrade() -> None:
    op.drop_column("tenants", "legal_document")
    op.drop_column("tenants", "legal_name")
    op.drop_index("idx_access_logs_created_at", table_name="access_logs")
    op.drop_table("access_logs")
