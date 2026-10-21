"""tenants.table_secret: signs the code in each table's QR Code (comanda)

Revision ID: 0008
Revises: 0007
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: Union[str, Sequence[str], None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("tenants", sa.Column("table_secret", sa.String(64), nullable=True))
    # 2 x 122 random bits from gen_random_uuid() (core since PostgreSQL 13), no extension needed.
    op.execute("UPDATE tenants SET table_secret = replace(gen_random_uuid()::text || gen_random_uuid()::text, '-', '')")
    op.alter_column("tenants", "table_secret", nullable=False)


def downgrade() -> None:
    op.drop_column("tenants", "table_secret")
