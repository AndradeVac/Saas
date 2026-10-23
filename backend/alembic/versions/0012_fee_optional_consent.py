"""optional service fee on table bills and the customer's consent to receive promotions (LGPD)

Revision ID: 0012
Revises: 0011
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0012"
down_revision: Union[str, Sequence[str], None] = "0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("tabs", sa.Column("service_fee_waived", sa.Boolean(), server_default=sa.false(), nullable=False))
    op.add_column("customers", sa.Column("marketing_opt_in", sa.Boolean(), server_default=sa.false(), nullable=False))
    op.add_column("customers", sa.Column("marketing_opt_in_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("customers", "marketing_opt_in_at")
    op.drop_column("customers", "marketing_opt_in")
    op.drop_column("tabs", "service_fee_waived")
