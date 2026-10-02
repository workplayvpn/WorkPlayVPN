from datetime import datetime
from sqlalchemy import BigInteger, String, Text, DateTime, ForeignKey, Integer, JSON, UniqueConstraint, CheckConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.session import Base

class SupportTicket(Base):
    __tablename__ = "support_tickets"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    category: Mapped[str] = mapped_column(String(24))
    tier: Mapped[str] = mapped_column(String(16))
    network: Mapped[str] = mapped_column(String(16))
    description: Mapped[str] = mapped_column(Text)
    diagnostics: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(16), default="new", server_default="new")
    response: Mapped[str | None] = mapped_column(Text, nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(64))
    revision: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    user_notified_revision: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    admin_notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (UniqueConstraint("user_id", "idempotency_key", name="uq_support_request"), CheckConstraint("status IN ('new','in_progress','resolved','closed')", name="ck_support_status"))
