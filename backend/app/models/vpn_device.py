from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class VpnDevice(Base):
    __tablename__ = "vpn_devices"

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    node_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("vpn_nodes.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    device_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    client_instance_id: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )
    xray_uuid: Mapped[str] = mapped_column(
        String(36),
        unique=True,
        index=True,
        nullable=False,
    )
    xray_email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
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
