from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import or_, select
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

    default_node_code = "nl-01"
    default_device_name = "Основное устройство"

    max_attempts = 8
    processing_lease_minutes = 5

    def recover_stale_processing(
        self,
        database: Session,
    ) -> int:
        now = datetime.now(UTC)

        stale_before = now - timedelta(
            minutes=self.processing_lease_minutes
        )

        fulfillments = list(
            database.scalars(
                select(PaymentFulfillment).where(
                    PaymentFulfillment.status == "processing",
                    PaymentFulfillment.processing_started_at
                    <= stale_before,
                )
            ).all()
        )

        for fulfillment in fulfillments:
            fulfillment.status = "pending"
            fulfillment.processing_started_at = None
            fulfillment.next_attempt_at = now

        if fulfillments:
            database.commit()

        return len(fulfillments)

    def claim_next(
        self,
        database: Session,
    ) -> PaymentFulfillment | None:
        now = datetime.now(UTC)

        fulfillment = database.scalar(
            select(PaymentFulfillment)
            .where(
                PaymentFulfillment.status == "pending",
                PaymentFulfillment.attempts
                < self.max_attempts,
                or_(
                    PaymentFulfillment.next_attempt_at.is_(None),
                    PaymentFulfillment.next_attempt_at <= now,
                ),
            )
            .order_by(
                PaymentFulfillment.created_at.asc()
            )
            .with_for_update(
                skip_locked=True
            )
        )

        if fulfillment is None:
            return None

        fulfillment.status = "processing"
        fulfillment.attempts += 1
        fulfillment.processing_started_at = now
        fulfillment.next_attempt_at = None

        database.commit()
        database.refresh(fulfillment)

        return fulfillment

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
        fulfillment.processing_started_at = None
        fulfillment.next_attempt_at = None
        fulfillment.last_error = None

        database.commit()

    def mark_failed(
        self,
        database: Session,
        fulfillment: PaymentFulfillment,
        error: str,
    ) -> None:
        now = datetime.now(UTC)

        fulfillment.last_error = error[:4000]
        fulfillment.processing_started_at = None

        if fulfillment.attempts >= self.max_attempts:
            fulfillment.status = "failed"
            fulfillment.next_attempt_at = None

        else:
            # 10s, 20s, 40s, 80s, 160s...
            # Максимум 30 минут.
            delay_seconds = min(
                10 * (2 ** (fulfillment.attempts - 1)),
                1800,
            )

            fulfillment.status = "pending"
            fulfillment.next_attempt_at = (
                now
                + timedelta(
                    seconds=delay_seconds
                )
            )

        database.commit()


payment_fulfillment_service = PaymentFulfillmentService()