"""annual billing, referrals and the log of lifecycle e-mails (each one sent once)

Revision ID: 0016
Revises: 0015
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0016"
down_revision: Union[str, Sequence[str], None] = "0015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("tenants", sa.Column("billing_cycle", sa.String(10), server_default="MONTHLY", nullable=False))
    op.add_column("tenants", sa.Column("referred_by", sa.String(40), nullable=True))
    op.create_table(
        "lifecycle_emails",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("key", sa.String(40), nullable=False),  # e.g. the week, so the weekly summary goes once a week
        sa.Column("sent_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("tenant_id", "kind", "key", name="uq_lifecycle_emails_once"),
    )
    op.execute("ALTER TABLE lifecycle_emails ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.drop_table("lifecycle_emails")
    op.drop_column("tenants", "referred_by")
    op.drop_column("tenants", "billing_cycle")
