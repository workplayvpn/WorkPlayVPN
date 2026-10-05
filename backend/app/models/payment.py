from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "users.id",
            ondelete="CASCADE",
        ),
        index=True,
        nullable=False,
    )

    purpose: Mapped[str] = mapped_column(String(16), default="subscription", server_default="subscription", nullable=False)
    is_gift_test: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)

    subscription_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "subscriptions.id",
            ondelete="RESTRICT",
        ),
        index=True,
        nullable=False,
    )

    provider: Mapped[str] = mapped_column(
        String(50),
        index=True,
        nullable=False,
    )

    provider_payment_id: Mapped[str | None] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=True,
    )

    idempotency_key: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(32),
        default="pending",
        server_default="pending",
        index=True,
        nullable=False,
    )

    amount: Mapped[Decimal] = mapped_column(
        Numeric(
            precision=10,
            scale=2,
        ),
        nullable=False,
    )

    currency: Mapped[str] = mapped_column(
        String(3),
        default="RUB",
        server_default="RUB",
        nullable=False,
    )

    confirmation_url: Mapped[str | None] = mapped_column(
        String(2048),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    paid_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
