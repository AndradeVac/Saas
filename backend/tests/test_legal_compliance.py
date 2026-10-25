"""Brazilian law checks: Marco Civil access records and the seller's identification on the menu."""
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update

from app.core.database import SessionLocal
from app.models.access_log import AccessLog
from app.models.tenant import Tenant
from app.services.access_log import RETENTION_DAYS, purge_old_access_logs


def _tenant_id(shop):
    with SessionLocal() as db:
        return db.scalar(select(Tenant.id).where(Tenant.slug == shop.slug))


def _logs(shop):
    with SessionLocal() as db:
        return db.scalars(select(AccessLog).where(AccessLog.tenant_id == _tenant_id(shop)).order_by(AccessLog.created_at)).all()


def test_login_and_orders_leave_an_access_record(make_tenant):
    shop = make_tenant()  # signs up and logs in
    product = shop.add_product("Pastel", "12.00")
    assert shop.public_order(product["id"], quantity=1).status_code == 201
    events = [log.event for log in _logs(shop)]
    assert {"SIGNUP", "LOGIN", "ORDER"} <= set(events)
    assert all(log.ip for log in _logs(shop))


def test_access_records_are_purged_after_six_months(make_tenant):
    shop = make_tenant()
    with SessionLocal() as db:
        db.execute(update(AccessLog).where(AccessLog.tenant_id == _tenant_id(shop))
                   .values(created_at=datetime.now(timezone.utc) - timedelta(days=RETENTION_DAYS + 1)))
        db.commit()
    purge_old_access_logs()
    assert _logs(shop) == []


def test_menu_shows_who_sells(make_tenant):
    shop = make_tenant()
    assert shop.patch("/tenant/settings", {"legal_document": "123"}).status_code == 422
    assert shop.patch("/tenant/settings", {"legal_name": "Pastelaria Exemplo LTDA", "legal_document": "63148827000167"}).status_code == 200
    menu = shop.public_get("/public/menu").json()["tenant"]
    assert menu["legal_name"] == "Pastelaria Exemplo LTDA" and menu["legal_document"] == "63.148.827/0001-67"
    assert shop.patch("/tenant/settings", {"legal_document": None}).json()["legal_document"] is None
