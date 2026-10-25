"""Account closure: by the owner (Settings) or after 60 days unpaid; the data is purged 30 days later."""
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select, update

from app.core.database import SessionLocal
from app.models.customer import Customer
from app.models.lifecycle_email import LifecycleEmail
from app.models.tenant import Tenant, TenantStatus
from app.services import closure
from tests.conftest import PASSWORD


def _row(shop):
    with SessionLocal() as db:
        return db.scalar(select(Tenant).where(Tenant.slug == shop.slug))


def _set(shop, **values):
    with SessionLocal() as db:
        db.execute(update(Tenant).where(Tenant.slug == shop.slug).values(**values))
        db.commit()


def test_owner_closes_the_account(make_tenant):
    shop = make_tenant()
    product = shop.add_product("Pastel", "12.00")
    assert shop.public_order(product["id"], quantity=1).status_code == 201

    assert shop.post("/tenant/close", {"password": "errada", "confirm_slug": shop.slug}).status_code == 422
    assert shop.post("/tenant/close", {"password": PASSWORD, "confirm_slug": "outra-loja"}).status_code == 422
    assert _row(shop).closed_at is None

    assert shop.post("/tenant/close", {"password": PASSWORD, "confirm_slug": shop.slug}).status_code == 204
    row = _row(shop)
    assert row.status is TenantStatus.SUSPENDED and row.closure_reason == "REQUEST" and row.closed_at is not None
    assert shop.public_get("/public/menu").status_code == 403  # offline right away
    assert shop.login().status_code == 403  # and nobody gets back in


def test_closed_account_is_purged_after_30_days(make_tenant):
    shop = make_tenant()
    product = shop.add_product("Pastel", "12.00")
    assert shop.public_order(product["id"], quantity=1).status_code == 201
    tenant_id = _row(shop).id
    assert shop.post("/tenant/close", {"password": PASSWORD, "confirm_slug": shop.slug}).status_code == 204

    closure.run()
    assert _row(shop) is not None  # still inside the 30 days: can be reactivated

    _set(shop, closed_at=datetime.now(timezone.utc) - timedelta(days=closure.PURGE_AFTER_DAYS + 1))
    assert closure.run()["purged"] >= 1
    assert _row(shop) is None
    with SessionLocal() as db:
        assert db.scalar(select(func.count(Customer.id)).where(Customer.tenant_id == tenant_id)) == 0


def test_reactivated_account_is_never_purged(make_tenant):
    shop = make_tenant()
    _set(shop, status=TenantStatus.ACTIVE, closed_at=datetime.now(timezone.utc) - timedelta(days=90), closure_reason="REQUEST")
    closure.run()
    assert _row(shop) is not None


def test_unpaid_account_is_warned_then_closed(make_tenant):
    shop = make_tenant()
    _set(shop, billing_status="OVERDUE", past_due_since=date.today() - timedelta(days=closure.UNPAID_WARNING_DAYS + 1))
    closure.run()
    row = _row(shop)
    assert row.status is not TenantStatus.SUSPENDED
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(LifecycleEmail).where(
            LifecycleEmail.tenant_id == row.id, LifecycleEmail.kind == "closing_unpaid")) == 1

    _set(shop, past_due_since=date.today() - timedelta(days=closure.UNPAID_CLOSE_DAYS))
    closure.run()
    row = _row(shop)
    assert row.status is TenantStatus.SUSPENDED and row.closure_reason == "UNPAID" and row.billing_status == "CANCELED"
