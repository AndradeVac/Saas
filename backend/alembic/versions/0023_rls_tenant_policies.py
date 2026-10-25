"""row level security per store: the database itself hides other stores' rows from request sessions

Until now RLS was enabled without policies, and the app connects as the tables' owner, which RLS skips: isolation
relied only on every query filtering by tenant_id. Now each tenant table has a policy keyed on the transaction
setting `app.tenant_id` (set by app.core.database for request sessions) and FORCE makes it apply to the owner too.
An empty setting lets everything through: background jobs, scripts, migrations and backups keep working unchanged.

Revision ID: 0023
Revises: 0022
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0023"
down_revision: Union[str, Sequence[str], None] = "0022"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SETTING = "NULLIF(current_setting('app.tenant_id', true), '')"
_UNSCOPED = f"{_SETTING} IS NULL"

TENANT_TABLES = (
    "access_logs", "audit_logs", "categories", "coupons", "customers", "lifecycle_emails", "media", "order_reviews",
    "orders", "password_reset_tokens", "products", "push_subscriptions", "tab_payments", "tabs", "users",
)
# No tenant_id of their own: they belong to an order, and the orders policy decides whether that order is visible.
ORDER_CHILD_TABLES = ("order_items", "order_status_history", "order_push_subscriptions")


def upgrade() -> None:
    for table in TENANT_TABLES:
        rule = f"({_UNSCOPED} OR tenant_id = {_SETTING}::uuid)"
        op.execute(f"CREATE POLICY tenant_isolation ON {table} FOR ALL USING {rule} WITH CHECK {rule}")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    for table in ORDER_CHILD_TABLES:
        rule = f"({_UNSCOPED} OR EXISTS (SELECT 1 FROM orders o WHERE o.id = {table}.order_id))"
        op.execute(f"CREATE POLICY tenant_isolation ON {table} FOR ALL USING {rule} WITH CHECK {rule}")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    # Stores: the request has to find its store by slug before it knows who it is, so reading is open (public data
    # plus settings the app never returns to another store); changing a store needs to be that store.
    op.execute("CREATE POLICY tenant_read ON tenants FOR SELECT USING (true)")
    own = f"({_UNSCOPED} OR id = {_SETTING}::uuid)"
    op.execute(f"CREATE POLICY tenant_insert ON tenants FOR INSERT WITH CHECK ({_UNSCOPED})")
    op.execute(f"CREATE POLICY tenant_update ON tenants FOR UPDATE USING {own} WITH CHECK {own}")
    op.execute(f"CREATE POLICY tenant_delete ON tenants FOR DELETE USING {own}")
    op.execute("ALTER TABLE tenants FORCE ROW LEVEL SECURITY")


def downgrade() -> None:
    for table in TENANT_TABLES + ORDER_CHILD_TABLES:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
    for name in ("tenant_read", "tenant_insert", "tenant_update", "tenant_delete"):
        op.execute(f"DROP POLICY IF EXISTS {name} ON tenants")
    op.execute("ALTER TABLE tenants NO FORCE ROW LEVEL SECURITY")
