from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class VpnNodeProfile(Base):
    __tablename__ = "vpn_node_profiles"

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )

    node_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "vpn_nodes.id",
            ondelete="CASCADE",
        ),
        index=True,
        nullable=False,
    )

    code: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        index=True,
        nullable=False,
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    protocol: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    network: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    security: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    port: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    flow: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )

    server_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    settings: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default="true",
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )