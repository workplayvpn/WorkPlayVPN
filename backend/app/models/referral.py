"""Money is stored as integer kopecks. No card details are stored here."""
from datetime import datetime
from sqlalchemy import BigInteger, Integer, String, DateTime, ForeignKey, CheckConstraint, UniqueConstraint, Index, text, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.session import Base

class ReferralAccount(Base):
    __tablename__ = "referral_accounts"
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    balance_kopecks: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0", nullable=False)

class ReferralInvite(Base):
    __tablename__ = "referral_invites"
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    referrer_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (CheckConstraint("user_id <> referrer_id", name="ck_referral_no_self"),)

class ReferralCommission(Base):
    __tablename__ = "referral_commissions"
    payment_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("payments.id", ondelete="CASCADE"), primary_key=True)
    referrer_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    gross_kopecks: Mapped[int] = mapped_column(BigInteger)
    amount_kopecks: Mapped[int] = mapped_column(BigInteger)
    refunded_kopecks: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")
    reversed_kopecks: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    __table_args__ = (CheckConstraint("gross_kopecks > 0 AND amount_kopecks > 0 AND refunded_kopecks BETWEEN 0 AND gross_kopecks AND reversed_kopecks BETWEEN 0 AND amount_kopecks", name="ck_referral_commission_amount"),)

class ReferralWithdrawal(Base):
    __tablename__ = "referral_withdrawals"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    amount_kopecks: Mapped[int] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String(20), default="requested", server_default="requested")
    idempotency_key: Mapped[str] = mapped_column(String(64))
    transfer_reference: Mapped[str | None] = mapped_column(String(200), nullable=True, unique=True)
    note: Mapped[str | None] = mapped_column(String(300), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    __table_args__ = (
        UniqueConstraint("user_id", "idempotency_key", name="uq_referral_withdrawal_key"),
        CheckConstraint("amount_kopecks >= 50000", name="ck_referral_withdrawal_minimum"),
        CheckConstraint("status IN ('requested','processing','paid','rejected','canceled')", name="ck_referral_withdrawal_status"),
        Index("uq_referral_open_withdrawal", "user_id", unique=True, postgresql_where=text("status IN ('requested','processing')"), sqlite_where=text("status IN ('requested','processing')")),
    )
