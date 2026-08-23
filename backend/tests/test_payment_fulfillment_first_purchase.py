from decimal import Decimal
from unittest.mock import patch

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.location import Location
from app.models.payment import Payment
from app.models.payment_fulfillment import PaymentFulfillment
from app.models.plan import Plan
from app.models.subscription import Subscription
from app.models.user import User
from app.models.vpn_device import VpnDevice
from app.models.vpn_node import VpnNode
from app.models.vpn_node_profile import VpnNodeProfile
from app.services.payment_fulfillment_service import (
    payment_fulfillment_service,
)
from app.services.payment_service import payment_service


def test_first_purchase_creates_device_and_vless() -> None:
    database = SessionLocal()

    try:
        user = User(
            telegram_id=995000001,
            username="first_purchase",
            first_name="FirstPurchase",
            is_active=True,
        )

        database.add(user)
        database.flush()

        assert (
            database.scalar(
                select(VpnDevice).where(
                    VpnDevice.user_id == user.id,
                    VpnDevice.is_active.is_(True),
                )
            )
            is None
        )

        plan = database.scalar(
            select(Plan).where(
                Plan.code == "standard_1m",
            )
        )

        assert plan is not None

        location = database.scalar(
            select(Location).where(
                Location.code == "NL",
            )
        )

        assert location is not None

        node = VpnNode(
            location_id=location.id,
            code="NL-01",
            name="Netherlands Test",
            host="vpn-test.example.com",
            ssh_port=22,
            ssh_user="test",
            is_active=True,
        )

        database.add(node)
        database.flush()

        profile = VpnNodeProfile(
            node_id=node.id,
            code="NL-01-REALITY",
            name="Netherlands Reality Test",
            protocol="vless",
            network="tcp",
            security="reality",
            port=443,
            flow="xtls-rprx-vision",
            server_name="example.com",
            settings={
                "fingerprint": "chrome",
                "public_key": "test-public-key",
                "short_id": "0123456789abcdef",
                "header_type": "none",
            },
            is_active=True,
        )

        database.add(profile)

        subscription = Subscription(
            user_id=user.id,
            plan_id=plan.id,
            status="pending",
        )

        database.add(subscription)
        database.flush()

        payment = Payment(
            user_id=user.id,
            subscription_id=subscription.id,
            provider="test",
            provider_payment_id=None,
            idempotency_key="first-purchase-001",
            status="pending",
            amount=Decimal("199.00"),
            currency="RUB",
            confirmation_url=None,
        )

        database.add(payment)
        database.commit()

        payment_service.mark_succeeded(
            database=database,
            payment_id=payment.id,
            provider_payment_id="provider-first-purchase-001",
        )

        fulfillment = database.scalar(
            select(PaymentFulfillment).where(
                PaymentFulfillment.payment_id == payment.id,
            )
        )

        assert fulfillment is not None
        assert fulfillment.status == "pending"

        claimed = payment_fulfillment_service.claim_next(
            database=database,
        )

        assert claimed is not None
        assert claimed.id == fulfillment.id
        assert claimed.status == "processing"

        fake_uuid = (
            "11111111-2222-3333-4444-555555555555"
        )

        with patch(
            "app.services.vpn_device_service."
            "xray_node_service.add_user",
            return_value=fake_uuid,
        ) as add_user:
            (
                result_user,
                result_payment,
                result_subscription,
                device,
                vless_url,
            ) = payment_fulfillment_service.build_access(
                database=database,
                fulfillment=claimed,
            )

        assert result_user.id == user.id
        assert result_payment.id == payment.id
        assert result_subscription.id == subscription.id

        assert device.user_id == user.id
        assert device.node_id == node.id
        assert device.device_name == "Основное устройство"
        assert device.is_active is True
        assert device.xray_uuid == fake_uuid

        add_user.assert_called_once()

        assert vless_url.startswith(
            f"vless://{fake_uuid}@vpn-test.example.com:443?"
        )

        assert "security=reality" in vless_url
        assert "type=tcp" in vless_url
        assert "sni=example.com" in vless_url
        assert "fp=chrome" in vless_url
        assert "pbk=test-public-key" in vless_url
        assert "sid=0123456789abcdef" in vless_url

        claimed_after_build = database.get(
            PaymentFulfillment,
            claimed.id,
        )

        assert claimed_after_build is not None
        assert claimed_after_build.device_id == device.id

        active_devices = list(
            database.scalars(
                select(VpnDevice).where(
                    VpnDevice.user_id == user.id,
                    VpnDevice.is_active.is_(True),
                )
            ).all()
        )

        assert len(active_devices) == 1

        # Повторный build_access не должен создавать
        # второе устройство.
        with patch(
            "app.services.vpn_device_service."
            "xray_node_service.add_user",
        ) as second_add_user:
            (
                _,
                _,
                _,
                second_device,
                second_vless_url,
            ) = payment_fulfillment_service.build_access(
                database=database,
                fulfillment=claimed,
            )

        assert second_device.id == device.id
        assert second_vless_url == vless_url
        second_add_user.assert_not_called()

        active_devices = list(
            database.scalars(
                select(VpnDevice).where(
                    VpnDevice.user_id == user.id,
                    VpnDevice.is_active.is_(True),
                )
            ).all()
        )

        assert len(active_devices) == 1

    finally:
        database.rollback()
        database.close()