"""account closure: when the store was closed (by the owner or for non-payment), so its data can be purged later

Revision ID: 0022
Revises: 0021
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0022"
down_revision: Union[str, Sequence[str], None] = "0021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("tenants", sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("tenants", sa.Column("closure_reason", sa.String(20), nullable=True))


def downgrade() -> None:
    op.drop_column("tenants", "closure_reason")
    op.drop_column("tenants", "closed_at")
