import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AccessLog(Base):
    """Marco Civil da Internet (Lei 12.965/2014, art. 15): application access records (IP + date/time) kept for
    6 months, handed over only by court order. Nothing else is stored here, and old rows are purged hourly."""

    __tablename__ = "access_logs"
    __table_args__ = (Index("idx_access_logs_created_at", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="SET NULL"), nullable=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    event: Mapped[str] = mapped_column(String(30), nullable=False)  # LOGIN, SIGNUP, ORDER (+ reference)
    reference: Mapped[str | None] = mapped_column(String(60), nullable=True)
    ip: Mapped[str] = mapped_column(String(45), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
