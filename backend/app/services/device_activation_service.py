import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.device_activation import DeviceActivation
from app.models.location import Location
from app.models.plan import Plan
from app.models.subscription import Subscription
from app.models.user import User
from app.models.vpn_device import VpnDevice
from app.models.vpn_node import VpnNode
from app.services.xray_node import xray_node_service


class DeviceActivationService:
    activation_ttl_minutes = 15

    def create_activation(
        self,
        database: Session,
        telegram_id: int,
        location_code: str,
    ) -> tuple[DeviceActivation, str]:
        user = database.scalar(
            select(User).where(
                User.telegram_id == telegram_id,
                User.is_active.is_(True),
            )
        )

        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        subscription = database.scalar(
            select(Subscription)
            .where(
                Subscription.user_id == user.id,
                Subscription.status == "active",
            )
            .order_by(Subscription.created_at.desc())
        )

        if subscription is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Active subscription required",
            )

        now = datetime.now(UTC)

        if (
            subscription.expires_at is not None
            and subscription.expires_at <= now
        ):
            subscription.status = "expired"
            database.commit()

            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Subscription expired",
            )

        plan = database.get(
            Plan,
            subscription.plan_id,
        )

        if plan is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Subscription plan not found",
            )

        active_devices = database.scalars(
            select(VpnDevice).where(
                VpnDevice.user_id == user.id,
                VpnDevice.is_active.is_(True),
            )
        ).all()

        device_limit = (
            plan.device_limit + user.extra_device_slots
        )

        if len(active_devices) >= device_limit:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Device limit reached",
            )

        location = database.scalar(
            select(Location).where(
                Location.code == location_code,
                Location.is_active.is_(True),
            )
        )

        if location is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Location not found",
            )

        raw_token = secrets.token_urlsafe(32)

        token_hash = hashlib.sha256(
            raw_token.encode("utf-8")
        ).hexdigest()

        activation = DeviceActivation(
            user_id=user.id,
            location_id=location.id,
            token_hash=token_hash,
            status="pending",
            expires_at=now
            + timedelta(
                minutes=self.activation_ttl_minutes
            ),
        )

        database.add(activation)
        database.commit()
        database.refresh(activation)

        return activation, raw_token

    def complete_activation(
        self,
        database: Session,
        raw_token: str,
        device_name: str,
    ) -> tuple[VpnDevice, VpnNode]:
        token_hash = hashlib.sha256(
            raw_token.encode("utf-8")
        ).hexdigest()

        activation = database.scalar(
            select(DeviceActivation).where(
                DeviceActivation.token_hash == token_hash
            )
        )

        if activation is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Activation not found",
            )

        now = datetime.now(UTC)

        if activation.status != "pending":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Activation already used",
            )

        if activation.expires_at <= now:
            activation.status = "expired"
            database.commit()

            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail="Activation expired",
            )

        user = database.scalar(
            select(User)
            .where(
                User.id == activation.user_id,
            )
            .with_for_update()
        )

        if user is None or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        subscription = database.scalar(
            select(Subscription)
            .where(
                Subscription.user_id == user.id,
                Subscription.status == "active",
            )
            .order_by(Subscription.created_at.desc())
        )

        if subscription is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Active subscription required",
            )

        if (
            subscription.expires_at is not None
            and subscription.expires_at <= now
        ):
            subscription.status = "expired"
            database.commit()

            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Subscription expired",
            )

        plan = database.get(
            Plan,
            subscription.plan_id,
        )

        if plan is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Subscription plan not found",
            )

        active_devices = database.scalars(
            select(VpnDevice).where(
                VpnDevice.user_id == user.id,
                VpnDevice.is_active.is_(True),
            )
        ).all()

        device_limit = (
            plan.device_limit + user.extra_device_slots
        )

        if len(active_devices) >= device_limit:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Device limit reached",
            )

        node = database.scalar(
            select(VpnNode)
            .where(
                VpnNode.location_id
                == activation.location_id,
                VpnNode.is_active.is_(True),
            )
            .order_by(VpnNode.id.asc())
        )

        if node is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="VPN node unavailable",
            )

        xray_email = (
            f"tg_{user.telegram_id}_"
            f"device_{uuid.uuid4().hex}"
            "@workplayvpn"
        )

        try:
            xray_uuid = xray_node_service.add_user(
                node=node,
                email=xray_email,
            )
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="VPN node unavailable",
            ) from exc

        device = VpnDevice(
            user_id=user.id,
            node_id=node.id,
            device_name=device_name,
            xray_uuid=xray_uuid,
            xray_email=xray_email,
            is_active=True,
        )

        try:
            database.add(device)
            database.flush()

            activation.device_id = device.id
            activation.status = "used"
            activation.used_at = now

            database.commit()
            database.refresh(device)

        except Exception:
            database.rollback()

            try:
                xray_node_service.remove_user(
                    node=node,
                    email=xray_email,
                )
            except Exception:
                pass

            raise

        return device, node


device_activation_service = DeviceActivationService()