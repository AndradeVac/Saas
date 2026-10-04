from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.user import User, UserRole


class UserRepository:
    def __init__(self, db: Session, tenant_id: UUID):
        self.db = db
        self.tenant_id = tenant_id

    def _base(self, include_inactive: bool = False):
        statement = select(User).where(User.tenant_id == self.tenant_id)
        if not include_inactive:
            statement = statement.where(User.active.is_(True))
        return statement

    def create(self, user: User) -> User:
        user.tenant_id = self.tenant_id
        self.db.add(user)
        self.db.flush()
        self.db.refresh(user)
        return user

    def get_by_id(self, user_id: UUID, include_inactive: bool = False) -> User | None:
        return self.db.scalar(self._base(include_inactive).where(User.id == user_id))

    def get_by_email(self, email: str, include_inactive: bool = False) -> User | None:
        return self.db.scalar(self._base(include_inactive).where(User.email == email))

    def get_all(self) -> list[User]:
        return list(self.db.scalars(self._base(include_inactive=True).order_by(User.name)).all())

    def update(self, user: User) -> User:
        self.db.flush()
        self.db.refresh(user)
        return user

    def count_active_admins(self) -> int:
        statement = select(func.count(User.id)).where(
            User.tenant_id == self.tenant_id,
            User.role == UserRole.ADMIN,
            User.active.is_(True),
        )
        return int(self.db.scalar(statement) or 0)
