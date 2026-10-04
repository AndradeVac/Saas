from uuid import UUID

from pwdlib import PasswordHash
from sqlalchemy.orm import Session

from app.core.exceptions import AuthenticationError, BusinessRuleError, NotFoundError
from app.models.user import User, UserRole
from app.repositories.user import UserRepository
from app.schemas.user import PasswordChange, PasswordReset, UserCreate, UserStatusUpdate, UserUpdate
from app.services.audit import record_audit


class UserService:
    password_hash = PasswordHash.recommended()
    # Verified when the e-mail does not exist, so response time does not reveal valid accounts.
    _dummy_hash = password_hash.hash("timing-guard-not-a-real-password")

    def __init__(self, db: Session, tenant_id: UUID):
        self.repository = UserRepository(db, tenant_id)
        self.tenant_id = tenant_id
        self.db = db

    def create(self, data: UserCreate, actor: User | None = None) -> User:
        user = User(
            name=data.name.strip(),
            email=data.email.strip().lower(),
            password_hash=self.password_hash.hash(data.password),
            role=data.role,
        )
        self.repository.create(user)
        record_audit(self.db, self.tenant_id, actor, "USER_CREATED", "USER", user.id, f"{user.email} role={user.role.value}")
        self.db.commit()
        return user

    def get_by_id(self, user_id: UUID) -> User:
        user = self.repository.get_by_id(user_id, include_inactive=True)
        if user is None:
            raise NotFoundError("Usuário não encontrado.")
        return user

    def get_all(self) -> list[User]:
        return self.repository.get_all()

    def update(self, user_id: UUID, data: UserUpdate, actor: User) -> User:
        user = self.get_by_id(user_id)
        if data.role is not None and data.role != user.role:
            if user.role is UserRole.ADMIN and user.active and self.repository.count_active_admins() <= 1:
                raise BusinessRuleError("O sistema precisa manter pelo menos um administrador ativo.")
            user.role = data.role
        if data.name is not None:
            user.name = data.name.strip()
        record_audit(self.db, self.tenant_id, actor, "USER_UPDATED", "USER", user.id, f"{user.email} role={user.role.value}")
        self.repository.update(user)
        self.db.commit()
        return user

    def update_status(self, user_id: UUID, data: UserStatusUpdate, actor: User) -> User:
        user = self.get_by_id(user_id)
        if not data.active and user.id == actor.id:
            raise BusinessRuleError("Você não pode desativar a própria conta.")
        if not data.active and user.role is UserRole.ADMIN and user.active and self.repository.count_active_admins() <= 1:
            raise BusinessRuleError("O sistema precisa manter pelo menos um administrador ativo.")
        user.active = data.active
        record_audit(self.db, self.tenant_id, actor, "USER_STATUS_CHANGED", "USER", user.id, f"{user.email} active={data.active}")
        self.repository.update(user)
        self.db.commit()
        return user

    def reset_password(self, user_id: UUID, data: PasswordReset, actor: User) -> None:
        user = self.get_by_id(user_id)
        user.password_hash = self.password_hash.hash(data.new_password)
        record_audit(self.db, self.tenant_id, actor, "PASSWORD_RESET", "USER", user.id, user.email)
        self.repository.update(user)
        self.db.commit()

    def change_password(self, user: User, data: PasswordChange) -> None:
        if not self.verify_password(data.current_password, user.password_hash):
            raise BusinessRuleError("A senha atual está incorreta.")
        user.password_hash = self.password_hash.hash(data.new_password)
        record_audit(self.db, self.tenant_id, user, "PASSWORD_CHANGED", "USER", user.id)
        self.repository.update(user)
        self.db.commit()

    def verify_password(self, plain_password: str, password_hash: str) -> bool:
        return self.password_hash.verify(plain_password, password_hash)

    def authenticate(self, email: str, password: str) -> User:
        user = self.repository.get_by_email(email.strip().lower())
        if user is None:
            self.verify_password(password, self._dummy_hash)
            raise AuthenticationError("E-mail ou senha inválidos.")
        if not self.verify_password(password, user.password_hash):
            raise AuthenticationError("E-mail ou senha inválidos.")
        return user
