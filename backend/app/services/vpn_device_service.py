import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.plan import Plan
from app.models.location import Location
from app.models.subscription import Subscription
from app.models.user import User
from app.models.vpn_device import VpnDevice
from app.models.vpn_node import VpnNode
from app.services.xray_node import xray_node_service



class VpnDeviceService:
    def create_device(
        self,
        database: Session,
        telegram_id: int,
        node_code: str,
        device_name: str,
        client_instance_id: str | None = None,
    ) -> VpnDevice:
        user = database.scalar(
            select(User)
            .where(
                User.telegram_id == telegram_id,
                User.is_active.is_(True),
            )
            .with_for_update()
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

        if client_instance_id is not None:
            existing_client_device = database.scalar(
                select(VpnDevice).where(
                    VpnDevice.user_id == user.id,
                    VpnDevice.client_instance_id == client_instance_id,
                    VpnDevice.is_active.is_(True),
                )
            )

            if existing_client_device is not None:
                return existing_client_device

        device_limit = (
            plan.device_limit
            + user.extra_device_slots
        )

        active_device_count = database.scalar(
            select(func.count(VpnDevice.id)).where(
                VpnDevice.user_id == user.id,
                VpnDevice.is_active.is_(True),
            )
        )

        if active_device_count >= device_limit:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Device limit reached",
            )

        node = database.scalar(
            select(VpnNode).where(
                VpnNode.code == node_code,
                VpnNode.is_active.is_(True),
            )
        )

        if node is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="VPN node not found",
            )

        existing_device = database.scalar(
            select(VpnDevice).where(
                VpnDevice.user_id == user.id,
                VpnDevice.device_name == device_name,
                VpnDevice.is_active.is_(True),
            )
        )

        if existing_device is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Device name already exists",
            )

        xray_email = (
            f"tg_{telegram_id}_"
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
            client_instance_id=client_instance_id,
            xray_uuid=xray_uuid,
            xray_email=xray_email,
            is_active=True,
        )

        try:
            database.add(device)
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

        return device

    def get_devices(
        self,
        database: Session,
        telegram_id: int,
    ) -> list[VpnDevice]:
        user = database.scalar(
            select(User).where(
                User.telegram_id == telegram_id,
            )
        )

        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        devices = list(
            database.scalars(
                select(VpnDevice)
                .where(
                    VpnDevice.user_id == user.id,
                    VpnDevice.is_active.is_(True),
                )
                .order_by(VpnDevice.created_at.asc())
            ).all()
        )

        return devices

    def remove_device(
        self,
        database: Session,
        telegram_id: int,
        device_id: int,
    ) -> VpnDevice:
        user = database.scalar(
            select(User).where(
                User.telegram_id == telegram_id,
            )
        )

        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        device = database.scalar(
            select(VpnDevice).where(
                VpnDevice.id == device_id,
                VpnDevice.user_id == user.id,
                VpnDevice.is_active.is_(True),
            )
        )

        if device is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Device not found",
            )

        node = database.get(
            VpnNode,
            device.node_id,
        )

        if node is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="VPN node not found",
            )

        try:
            xray_node_service.remove_user(
                node=node,
                email=device.xray_email,
            )
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="VPN node unavailable",
            ) from exc

        device.is_active = False

        try:
            database.commit()
            database.refresh(device)
        except Exception:
            database.rollback()

            # Xray user was already removed, so this is an
            # exceptional state that we must not silently hide.
            raise

        return device

    def change_location(
        self,
        database: Session,
        telegram_id: int,
        device_id: int,
        location_code: str,
    ) -> VpnDevice:
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

        device = database.scalar(
            select(VpnDevice).where(
                VpnDevice.id == device_id,
                VpnDevice.user_id == user.id,
                VpnDevice.is_active.is_(True),
            )
        )

        if device is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Device not found",
            )

        current_node = database.get(
            VpnNode,
            device.node_id,
        )

        if current_node is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="VPN node not found",
            )

        location = database.scalar(
            select(Location).where(
                Location.code == location_code.upper(),
                Location.is_active.is_(True),
            )
        )

        if location is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Location not found",
            )

        if current_node.location_id == location.id:
            return device

        target_node = database.scalar(
            select(VpnNode)
            .where(
                VpnNode.location_id == location.id,
                VpnNode.is_active.is_(True),
            )
            .order_by(VpnNode.id.asc())
        )

        if target_node is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="VPN node unavailable",
            )

        try:
            xray_node_service.add_user(
                node=target_node,
                email=device.xray_email,
                user_uuid=device.xray_uuid,
            )
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Target VPN node unavailable",
            ) from exc

        try:
            xray_node_service.remove_user(
                node=current_node,
                email=device.xray_email,
            )
        except Exception as exc:
            try:
                xray_node_service.remove_user(
                    node=target_node,
                    email=device.xray_email,
                )
            except Exception:
                pass

            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Current VPN node unavailable",
            ) from exc

        device.node_id = target_node.id

        try:
            database.commit()
            database.refresh(device)
        except Exception:
            database.rollback()

            try:
                xray_node_service.remove_user(
                    node=target_node,
                    email=device.xray_email,
                )
                xray_node_service.add_user(
                    node=current_node,
                    email=device.xray_email,
                    user_uuid=device.xray_uuid,
                )
            except Exception:
                pass

            raise

        return device


vpn_device_service = VpnDeviceService()
