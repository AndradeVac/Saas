"""call the waiter from the table (with the reason)

Revision ID: 0020
Revises: 0019
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0020"
down_revision: Union[str, Sequence[str], None] = "0019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("tabs", sa.Column("waiter_call", sa.String(30), nullable=True))
    op.add_column("tabs", sa.Column("waiter_called_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("tabs", "waiter_called_at")
    op.drop_column("tabs", "waiter_call")
