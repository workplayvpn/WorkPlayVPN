from datetime import datetime
import secrets

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


def new_device_public_id() -> str:
    return "WP-" + secrets.token_hex(8).upper()


class VpnDevice(Base):
    __tablename__ = "vpn_devices"

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )
    public_id: Mapped[str] = mapped_column(
        String(24), unique=True, nullable=False,
        default=new_device_public_id,
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
    mobile_xray_uuid: Mapped[str | None] = mapped_column(
        String(36),
        unique=True,
        index=True,
        nullable=True,
    )
    mobile_xray_email: Mapped[str | None] = mapped_column(
        String(255),
        unique=True,
        index=True,
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
