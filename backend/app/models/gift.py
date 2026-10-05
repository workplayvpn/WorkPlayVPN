from datetime import datetime
from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.session import Base


class GiftCertificate(Base):
    __tablename__ = "gift_certificates"
    __table_args__ = (
        CheckConstraint("access_tier IN ('basic', 'mobile')", name="ck_gifts_tier"),
        CheckConstraint("duration_days > 0 AND device_limit > 0", name="ck_gifts_terms"),
        CheckConstraint("state IN ('pending', 'ready', 'redeemed')", name="ck_gifts_state"),
        CheckConstraint("state = 'pending' OR (code_hash IS NOT NULL AND issued_at IS NOT NULL)", name="ck_gifts_issued"),
        CheckConstraint("state != 'redeemed' OR (recipient_id IS NOT NULL AND redeemed_at IS NOT NULL AND redeemed_subscription_id IS NOT NULL)", name="ck_gifts_redeemed"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    payment_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("payments.id", ondelete="RESTRICT"), unique=True)
    buyer_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    plan_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("plans.id", ondelete="RESTRICT"))
    access_tier: Mapped[str] = mapped_column(String(16))
    duration_days: Mapped[int] = mapped_column(Integer)
    device_limit: Mapped[int] = mapped_column(Integer)
    state: Mapped[str] = mapped_column(String(16), default="pending", server_default="pending")
    code_hash: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    recipient_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="RESTRICT"), nullable=True, index=True)
    redeemed_subscription_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("subscriptions.id", ondelete="RESTRICT"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    redeemed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class GiftAttemptWindow(Base):
    __tablename__ = "gift_attempt_windows"
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
