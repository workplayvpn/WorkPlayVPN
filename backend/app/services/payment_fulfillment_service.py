from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.payment import Payment
from app.models.payment_fulfillment import PaymentFulfillment
from app.models.subscription import Subscription
from app.models.user import User
from app.models.vpn_device import VpnDevice
from app.models.vpn_node import VpnNode
from app.services.vpn_device_service import vpn_device_service
from app.services.vpn_node_profile_service import (
    vpn_node_profile_service,
)
from app.services.vpn_profile_link_builder import (
    vpn_profile_link_builder,
)


class PaymentFulfillmentService:

    default_node_code = "NL-01"
    default_device_name = "Основное устройство"

    def get_next_pending(
        self,
        database: Session,
    ) -> PaymentFulfillment | None:
        return database.scalar(
            select(PaymentFulfillment)
            .where(
                PaymentFulfillment.status == "pending",
            )
            .order_by(
                PaymentFulfillment.created_at.asc()
            )
            .with_for_update(
                skip_locked=True
            )
        )

    def build_access(
        self,
        database: Session,
        fulfillment: PaymentFulfillment,
    ) -> tuple[
        User,
        Payment,
        Subscription,
        VpnDevice,
        str,
    ]:
        payment = database.get(
            Payment,
            fulfillment.payment_id,
        )

        if payment is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Fulfillment payment not found",
            )

        user = database.get(
            User,
            fulfillment.user_id,
        )

        if user is None or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        subscription = database.get(
            Subscription,
            payment.subscription_id,
        )

        if subscription is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Subscription not found",
            )

        if payment.status != "succeeded":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Payment is not succeeded",
            )

        active_device = database.scalar(
            select(VpnDevice)
            .where(
                VpnDevice.user_id == user.id,
                VpnDevice.is_active.is_(True),
            )
            .order_by(
                VpnDevice.created_at.asc()
            )
        )

        if active_device is None:
            active_device = vpn_device_service.create_device(
                database=database,
                telegram_id=user.telegram_id,
                node_code=self.default_node_code,
                device_name=self.default_device_name,
            )

        node = database.get(
            VpnNode,
            active_device.node_id,
        )

        if node is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="VPN node not found",
            )

        profiles = (
            vpn_node_profile_service.get_active_profiles_for_nodes(
                database=database,
                node_ids={node.id},
            )
        )

        reality_profile = next(
            (
                profile
                for profile in profiles
                if profile.node_id == node.id
                and profile.protocol == "vless"
                and profile.network == "tcp"
                and profile.security == "reality"
            ),
            None,
        )

        if reality_profile is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="VPN Reality profile not found",
            )

        vless_url = vpn_profile_link_builder.build_vless_link(
            device=active_device,
            node=node,
            profile=reality_profile,
        )

        fulfillment.device_id = active_device.id

        return (
            user,
            payment,
            subscription,
            active_device,
            vless_url,
        )

    def mark_delivered(
        self,
        database: Session,
        fulfillment: PaymentFulfillment,
    ) -> None:
        fulfillment.status = "delivered"
        fulfillment.delivered_at = datetime.now(UTC)
        fulfillment.last_error = None

        database.commit()

    def mark_failed(
        self,
        database: Session,
        fulfillment: PaymentFulfillment,
        error: str,
    ) -> None:
        fulfillment.attempts += 1
        fulfillment.last_error = error[:4000]

        database.commit()


payment_fulfillment_service = PaymentFulfillmentService()