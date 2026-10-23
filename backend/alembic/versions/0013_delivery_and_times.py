"""estimated times, delivery zones (neighbourhood -> fee) and PIX up front for deliveries

Revision ID: 0013
Revises: 0012
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0013"
down_revision: Union[str, Sequence[str], None] = "0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("tenants", sa.Column("prep_minutes", sa.SmallInteger(), server_default="20", nullable=False))
    op.add_column("tenants", sa.Column("delivery_minutes", sa.SmallInteger(), server_default="45", nullable=False))
    op.add_column("tenants", sa.Column("delivery_zones", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False))
    op.add_column("tenants", sa.Column("require_pix_delivery", sa.Boolean(), server_default=sa.false(), nullable=False))


def downgrade() -> None:
    for column in ("require_pix_delivery", "delivery_zones", "delivery_minutes", "prep_minutes"):
        op.drop_column("tenants", column)
