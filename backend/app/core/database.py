from collections.abc import Iterator

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    pass


engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_recycle=1800,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_timeout=20,
    # Neon's pooler (PgBouncer) multiplexes connections: keep server-side prepared statements off.
    connect_args={"prepare_threshold": None},
)


if settings.db_role:
    if not settings.db_role.replace("_", "").isalnum():
        raise ValueError("DB_ROLE must be a plain role name")

    @event.listens_for(engine, "connect")
    def _set_role(dbapi_connection, connection_record) -> None:
        with dbapi_connection.cursor() as cursor:
            cursor.execute(f"SET ROLE {settings.db_role}")
        dbapi_connection.commit()


SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)


# Row Level Security (migration 0023). Every tenant table has a policy that only shows rows of the store in the
# `app.tenant_id` setting; when the setting is empty the policy lets everything through. So:
# - request sessions (get_db) start locked on NO_TENANT (sees nothing) until get_tenant() names the store, and a
#   query that forgets its tenant_id filter still cannot reach another store's rows;
# - platform routes that must see several stores (sign-up, Asaas webhook, /admin, public images) call
#   allow_all_tenants();
# - background jobs, scripts, migrations and backups use plain SessionLocal / their own connection: unrestricted.
# The setting is transaction-local, re-applied at the start of every transaction, so it never leaks to the next
# request that reuses the pooled connection.
NO_TENANT = "00000000-0000-0000-0000-000000000000"
_RLS_KEY = "rls_tenant"


def _apply_rls(session: Session, connection) -> None:
    if _RLS_KEY in session.info:
        connection.execute(text("SELECT set_config('app.tenant_id', :tenant, true)"), {"tenant": session.info[_RLS_KEY]})


@event.listens_for(SessionLocal, "after_begin")
def _on_begin(session: Session, transaction, connection) -> None:
    _apply_rls(session, connection)


def set_tenant_scope(db: Session, tenant_id) -> None:
    """From now on this session only sees rows of this store (also in the transaction already open)."""
    db.info[_RLS_KEY] = str(tenant_id)
    if db.in_transaction():
        _apply_rls(db, db.connection())


def allow_all_tenants(db: Session) -> None:
    """Platform routes that legitimately work across stores. Use sparingly."""
    db.info[_RLS_KEY] = ""
    if db.in_transaction():
        _apply_rls(db, db.connection())


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    db.info[_RLS_KEY] = NO_TENANT  # locked until get_tenant() (or allow_all_tenants) says otherwise
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
