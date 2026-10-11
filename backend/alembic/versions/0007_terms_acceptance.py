"""tenants: when and which version of the terms the owner accepted at sign-up

Revision ID: 0007
Revises: 0006
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: Union[str, Sequence[str], None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("tenants", sa.Column("terms_accepted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("tenants", sa.Column("terms_version", sa.String(20), nullable=True))


def downgrade() -> None:
    op.drop_column("tenants", "terms_version")
    op.drop_column("tenants", "terms_accepted_at")
