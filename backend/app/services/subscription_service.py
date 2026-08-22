from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.plan import Plan  # noqa: F401
from app.models.subscription import Subscription
from app.models.user import User
from app.models.vpn_device import VpnDevice
from app.models.vpn_node import VpnNode
from app.services.xray_node import xray_node_service


class SubscriptionService:

    def get_active_subscription(
        self,
        database: Session,
        user_id: int,
    ) -> Subscription | None:
        return database.scalar(
            select(Subscription)
            .where(
                Subscription.user_id == user_id,
                Subscription.status == "active",
            )
            .order_by(
                Subscription.created_at.desc()
            )
        )

    def expire_subscription(
        self,
        database: Session,
        subscription: Subscription,
    ) -> Subscription:
        if subscription.status != "active":
            return subscription

        devices = list(
            database.scalars(
                select(VpnDevice).where(
                    VpnDevice.user_id == subscription.user_id,
                    VpnDevice.is_active.is_(True),
                )
            ).all()
        )

        revoked_devices: list[
            tuple[VpnDevice, VpnNode]
        ] = []

        try:
            for device in devices:
                node = database.get(
                    VpnNode,
                    device.node_id,
                )

                if node is None:
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="VPN node not found",
                    )

                xray_node_service.remove_user(
                    node=node,
                    email=device.xray_email,
                )

                revoked_devices.append(
                    (
                        device,
                        node,
                    )
                )

            subscription.status = "expired"

            database.commit()
            database.refresh(subscription)

        except Exception as exc:
            database.rollback()

            for revoked_device, revoked_node in reversed(
                revoked_devices
            ):
                try:
                    xray_node_service.add_user(
                        node=revoked_node,
                        email=revoked_device.xray_email,
                        user_uuid=revoked_device.xray_uuid,
                    )
                except Exception:
                    pass

            if isinstance(
                exc,
                HTTPException,
            ):
                raise

            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Failed to expire subscription safely",
            ) from exc

        return subscription

    def expire_if_needed(
        self,
        database: Session,
        subscription: Subscription,
    ) -> Subscription:
        if subscription.status != "active":
            return subscription

        if subscription.expires_at is None:
            return subscription

        now = datetime.now(UTC)

        if subscription.expires_at <= now:
            return self.expire_subscription(
                database=database,
                subscription=subscription,
            )

        return subscription

    def restore_user_access(
        self,
        database: Session,
        user_id: int,
    ) -> None:
        user = database.get(
            User,
            user_id,
        )

        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        devices = list(
            database.scalars(
                select(VpnDevice).where(
                    VpnDevice.user_id == user.id,
                    VpnDevice.is_active.is_(True),
                )
            ).all()
        )

        restored_devices: list[
            tuple[VpnDevice, VpnNode]
        ] = []

        try:
            for device in devices:
                node = database.get(
                    VpnNode,
                    device.node_id,
                )

                if node is None:
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="VPN node not found",
                    )

                xray_node_service.add_user(
                    node=node,
                    email=device.xray_email,
                    user_uuid=device.xray_uuid,
                )

                restored_devices.append(
                    (
                        device,
                        node,
                    )
                )

        except Exception as exc:
            for restored_device, restored_node in reversed(
                restored_devices
            ):
                try:
                    xray_node_service.remove_user(
                        node=restored_node,
                        email=restored_device.xray_email,
                    )
                except Exception:
                    pass

            if isinstance(
                exc,
                HTTPException,
            ):
                raise

            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="VPN node unavailable",
            ) from exc


subscription_service = SubscriptionService()