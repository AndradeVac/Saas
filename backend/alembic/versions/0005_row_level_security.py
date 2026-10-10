"""row level security on every table (defense in depth)

The API connects as the tables' owner, which bypasses RLS (it is not FORCEd), so the app is unaffected.
Any other role that is ever granted access to these tables (e.g. Supabase's anon/authenticated through the
Data API) sees nothing, because no policies exist. New tables must enable RLS in their own migration.

Revision ID: 0005
Revises: 0004
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0005"
down_revision: Union[str, Sequence[str], None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLES = (
    "alembic_version", "tenants", "users", "categories", "products", "customers", "orders", "order_items",
    "order_status_history", "coupons", "media", "audit_logs", "tabs",
)


def upgrade() -> None:
    for table in TABLES:
        op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')


def downgrade() -> None:
    for table in TABLES:
        op.execute(f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY')
