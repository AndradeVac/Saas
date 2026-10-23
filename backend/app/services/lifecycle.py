"""Automatic e-mails to the store owner: welcome, end of the trial, payment overdue, weekly summary and a nudge
when the first order does not come. Each e-mail goes out once (unique row in lifecycle_emails), so running the job
on every process / every hour is safe."""
from __future__ import annotations

import html
import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.email import send_email
from app.models.lifecycle_email import LifecycleEmail
from app.models.order import Order, OrderStatus
from app.models.order_item import OrderItem
from app.models.tenant import Tenant, TenantStatus
from app.models.user import User, UserRole

logger = logging.getLogger(__name__)


def _owner_email(db: Session, tenant: Tenant) -> tuple[str, str] | None:
    owner = db.scalar(select(User).where(User.tenant_id == tenant.id, User.role == UserRole.ADMIN, User.active.is_(True)).order_by(User.created_at))
    return (owner.email, owner.name.split(" ")[0]) if owner else None


def _layout(tenant: Tenant, title: str, paragraphs: list[str], cta: str, link: str) -> tuple[str, str]:
    color = tenant.primary_color or "#c2410c"
    body = "".join(f'<p style="margin:0 0 14px;line-height:1.55">{p}</p>' for p in paragraphs)
    page = f"""<div style="font-family:Arial,Helvetica,sans-serif;background:#f5f5f4;padding:24px">
  <div style="max-width:560px;margin:0 auto;background:#fff;border-radius:14px;overflow:hidden;border:1px solid #e7e5e4">
    <div style="background:{color};color:#fff;padding:18px 24px;font-size:18px;font-weight:bold">{html.escape(tenant.name.strip())}</div>
    <div style="padding:24px;color:#1c1917;font-size:15px">
      <h2 style="margin:0 0 14px;font-size:20px">{title}</h2>{body}
      <a href="{link}" style="display:inline-block;background:{color};color:#fff;text-decoration:none;padding:12px 20px;border-radius:10px;font-weight:bold">{cta}</a>
    </div>
    <div style="padding:14px 24px;color:#78716c;font-size:12px;border-top:1px solid #e7e5e4">Mesa Digital · mesadig.com.br · Você recebe este e-mail por ter uma conta no Mesa Digital.</div>
  </div></div>"""
    text = f"{title}\n\n" + "\n\n".join(html.unescape(p.replace("<strong>", "").replace("</strong>", "")) for p in paragraphs) + f"\n\n{cta}: {link}"
    return page, text


def send_once(db: Session, tenant: Tenant, kind: str, key: str, title: str, paragraphs: list[str], cta: str, path: str) -> bool:
    """Registers the e-mail first (the unique key wins any race between processes), then sends it."""
    recipient = _owner_email(db, tenant)
    if recipient is None:
        return False
    try:
        with db.begin_nested():
            db.add(LifecycleEmail(tenant_id=tenant.id, kind=kind, key=key))
        db.commit()
    except IntegrityError:
        db.rollback()
        return False
    email, name = recipient
    page, text = _layout(tenant, title.replace("{nome}", name), [p.replace("{nome}", name) for p in paragraphs], cta, settings.tenant_url(tenant.slug, path))
    return send_email(email, title.replace("{nome}", name), page, text)


def welcome(tenant_id: UUID) -> None:
    with SessionLocal() as db:
        tenant = db.get(Tenant, tenant_id)
        if tenant is None:
            return
        send_once(db, tenant, "welcome", "-", "Bem-vindo ao Mesa Digital, {nome}!", [
            f"Seu cardápio <strong>{html.escape(tenant.name.strip())}</strong> já está no ar. Nos próximos {settings.trial_days} dias está tudo liberado para você testar com clientes de verdade.",
            "Para começar bem: <strong>1)</strong> cadastre os produtos (ou importe o cardápio por foto), <strong>2)</strong> coloque logo e cor, <strong>3)</strong> imprima os QR Codes das mesas e <strong>4)</strong> faça um pedido de teste pelo celular.",
            "Qualquer dúvida, é só responder este e-mail.",
        ], "Abrir meu painel", "/painel")


def payment_overdue(db: Session, tenant: Tenant) -> None:
    key = (tenant.past_due_since or datetime.now(timezone.utc).date()).isoformat()
    send_once(db, tenant, "payment_overdue", key, "{nome}, o pagamento da assinatura não foi identificado", [
        f"A cobrança do seu plano no Mesa Digital está em aberto. Você tem <strong>{settings.billing_grace_days} dias</strong> para pagar antes de o cardápio parar de receber pedidos.",
        "É rápido: PIX, boleto ou cartão, direto pelo painel.",
    ], "Pagar agora", "/painel/plano")


def _weekly(db: Session, tenant: Tenant, now: datetime) -> None:
    zone = ZoneInfo(tenant.timezone)
    week_start = datetime(now.year, now.month, now.day, tzinfo=zone) - timedelta(days=7)
    previous_start = week_start - timedelta(days=7)
    base = [Order.tenant_id == tenant.id, Order.status != OrderStatus.CANCELLED]
    revenue, orders = db.execute(select(func.coalesce(func.sum(Order.total), 0), func.count(Order.id))
                                 .where(*base, Order.created_at >= week_start, Order.created_at < week_start + timedelta(days=7))).one()
    if not orders:
        return
    previous = Decimal(db.scalar(select(func.coalesce(func.sum(Order.total), 0)).where(*base, Order.created_at >= previous_start, Order.created_at < week_start)) or 0)
    top = db.execute(select(OrderItem.product_name, func.sum(OrderItem.quantity)).join(Order, Order.id == OrderItem.order_id)
                     .where(*base, Order.created_at >= week_start).group_by(OrderItem.product_name).order_by(func.sum(OrderItem.quantity).desc()).limit(1)).first()
    money = lambda value: "R$ " + f"{Decimal(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")  # noqa: E731
    change = ""
    if previous:
        pct = (Decimal(revenue) - previous) / previous * 100
        change = f" ({'+' if pct >= 0 else ''}{pct:.0f}% em relação à semana anterior)".replace(".", ",")
    iso = now.isocalendar()
    send_once(db, tenant, "weekly", f"{iso.year}-W{iso.week:02d}", "{nome}, seu resumo da semana", [
        f"Nos últimos 7 dias você vendeu <strong>{money(revenue)}</strong> em <strong>{orders} pedidos</strong>{change}.",
        f"Mais pedido: <strong>{html.escape(top[0])}</strong> ({int(top[1])} unidades)." if top else "",
        "Veja horários de pico, clientes que sumiram e o que mais dá lucro nas Análises.",
    ], "Ver meus números", "/painel")


def run(now: datetime | None = None) -> int:
    """Checks every store; sends what is due. Returns how many e-mails were attempted."""
    sent = 0
    with SessionLocal() as db:
        for tenant in db.scalars(select(Tenant).where(Tenant.status != TenantStatus.SUSPENDED)):
            local = (now or datetime.now(timezone.utc)).astimezone(ZoneInfo(tenant.timezone))
            if not 9 <= local.hour < 20:
                continue  # never at night
            try:
                if tenant.status is TenantStatus.TRIAL and tenant.trial_ends_at:
                    days_left = (tenant.trial_ends_at.astimezone(local.tzinfo).date() - local.date()).days
                    end = tenant.trial_ends_at.date().isoformat()
                    if days_left == 3:
                        sent += send_once(db, tenant, "trial_3d", end, "{nome}, faltam 3 dias do seu teste", [
                            "Seu período de teste do Mesa Digital termina em 3 dias. Para continuar recebendo pedidos sem interrupção, escolha um plano.",
                            "No plano anual você paga 10 meses e usa 12.",
                        ], "Escolher meu plano", "/painel/plano")
                    elif days_left == 0:
                        sent += send_once(db, tenant, "trial_last_day", end, "Hoje é o último dia do seu teste", [
                            "A partir de amanhã o cardápio continua no ar, mas deixa de receber pedidos até você escolher um plano. Seus produtos e clientes ficam salvos.",
                        ], "Assinar agora", "/painel/plano")
                    elif -3 <= days_left < 0:
                        sent += send_once(db, tenant, "trial_expired", end, "{nome}, seu cardápio parou de receber pedidos", [
                            "O teste terminou. Assine em 1 minuto e volte a receber pedidos na hora: está tudo salvo do jeito que você deixou.",
                        ], "Reativar meu cardápio", "/painel/plano")
                    has_orders = db.scalar(select(func.count(Order.id)).where(Order.tenant_id == tenant.id)) or 0
                    created = tenant.created_at.astimezone(local.tzinfo).date() if tenant.created_at else local.date()
                    if not has_orders and (local.date() - created).days >= 3:
                        sent += send_once(db, tenant, "first_order_help", "-", "{nome}, posso ajudar com o primeiro pedido?", [
                            "Vi que o seu cardápio ainda não recebeu nenhum pedido. Uma dica que funciona: faça um pedido de teste lendo o QR Code de uma mesa e mande o link do cardápio no WhatsApp dos clientes.",
                            "Se quiser, nós cadastramos o seu cardápio para você: é só responder este e-mail.",
                        ], "Ver meu cardápio", "/painel")
                if local.weekday() == 0:  # Monday
                    _weekly(db, tenant, local)
            except Exception:
                db.rollback()
                logger.exception("Lifecycle e-mails failed for %s", tenant.slug)
    return sent
