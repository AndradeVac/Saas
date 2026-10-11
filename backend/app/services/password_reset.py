""""Esqueci minha senha": a one-hour, single-use link sent by e-mail to the account's address."""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from html import escape

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.email import send_email
from app.core.exceptions import BusinessRuleError
from app.models.password_reset import PasswordResetToken
from app.models.tenant import Tenant
from app.models.user import User
from app.repositories.user import UserRepository
from app.services.audit import record_audit
from app.services.user import UserService

TOKEN_TTL = timedelta(hours=1)


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class PasswordResetService:
    def __init__(self, db: Session, tenant: Tenant):
        self.db = db
        self.tenant = tenant

    def request(self, email: str) -> None:
        """Always succeeds from the caller's point of view, so it never reveals which e-mails exist."""
        user = UserRepository(self.db, self.tenant.id).get_by_email(email.strip().lower())
        if user is None:
            return
        now = datetime.now(timezone.utc)
        self._invalidate(user, now)
        token = secrets.token_urlsafe(32)
        self.db.add(PasswordResetToken(tenant_id=self.tenant.id, user_id=user.id, token_hash=_hash(token), expires_at=now + TOKEN_TTL))
        record_audit(self.db, self.tenant.id, user, "PASSWORD_RESET_REQUESTED", "USER", user.id, user.email)
        self.db.commit()

        link = settings.tenant_url(self.tenant.slug, f"/redefinir-senha?token={token}")
        name = escape(user.name.split()[0])
        business = escape(self.tenant.name)
        send_email(
            user.email,
            f"Redefinir sua senha · {self.tenant.name}",
            html=(
                f"<p>Olá, {name}!</p>"
                f"<p>Recebemos um pedido para redefinir a senha do painel de <strong>{business}</strong>.</p>"
                f'<p><a href="{escape(link)}" style="display:inline-block;padding:12px 20px;background:#c2410c;color:#fff;'
                f'border-radius:10px;text-decoration:none;font-weight:600">Criar nova senha</a></p>'
                "<p>O link vale por 1 hora e só pode ser usado uma vez. Se você não pediu, ignore este e-mail: "
                "sua senha atual continua valendo.</p>"
            ),
            text=(
                f"Olá, {user.name.split()[0]}!\n\nPara criar uma nova senha do painel de {self.tenant.name}, abra:\n{link}\n\n"
                "O link vale por 1 hora. Se você não pediu, ignore este e-mail."
            ),
        )

    def reset(self, token: str, new_password: str) -> None:
        now = datetime.now(timezone.utc)
        row = self.db.scalar(
            select(PasswordResetToken).where(
                PasswordResetToken.tenant_id == self.tenant.id,
                PasswordResetToken.token_hash == _hash(token),
            ).with_for_update()
        )
        if row is None or row.used_at is not None or row.expires_at <= now:
            raise BusinessRuleError("Este link é inválido ou expirou. Peça um novo em “Esqueci minha senha”.")
        user = self.db.get(User, row.user_id)
        if user is None or not user.active or user.tenant_id != self.tenant.id:
            raise BusinessRuleError("Este link é inválido ou expirou. Peça um novo em “Esqueci minha senha”.")
        user.password_hash = UserService.password_hash.hash(new_password)
        row.used_at = now
        self._invalidate(user, now)
        record_audit(self.db, self.tenant.id, user, "PASSWORD_RESET_COMPLETED", "USER", user.id, user.email)
        self.db.commit()

    def _invalidate(self, user: User, now: datetime) -> None:
        self.db.execute(
            update(PasswordResetToken)
            .where(PasswordResetToken.user_id == user.id, PasswordResetToken.used_at.is_(None))
            .values(used_at=now)
        )
