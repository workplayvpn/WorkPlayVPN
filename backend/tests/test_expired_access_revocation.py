import hashlib
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy import delete, select

from app.db.session import SessionLocal
from app.models.device_activation import DeviceActivation
from app.models.location import Location
from app.models.plan import Plan
from app.models.subscription import Subscription
from app.models.user import User
from app.models.vpn_device import VpnDevice
from app.models.vpn_node import VpnNode
from app.services.device_activation_service import device_activation_service
from app.services.vpn_device_service import vpn_device_service
from app.services.xray_node import xray_node_service


TELEGRAM_ID = 993100021
NODE_CODE = "expired-access-test-node"
RAW_TOKEN = "expired-access-test-token"


@pytest.fixture
def expired_access():
    with SessionLocal() as db:
        db.execute(delete(User).where(User.telegram_id == TELEGRAM_ID))
        db.execute(delete(VpnNode).where(VpnNode.code == NODE_CODE))
        db.commit()

        location = db.scalar(select(Location).where(Location.code == "NL"))
        plan = db.scalar(select(Plan).where(Plan.code == "trial_1d"))
        assert location is not None and plan is not None

        user = User(telegram_id=TELEGRAM_ID, first_name="Expiry test", is_active=True)
        node = VpnNode(
            location_id=location.id, code=NODE_CODE, name="Expiry test",
            host="192.0.2.21", ssh_user="test", is_active=True,
        )
        db.add_all([user, node])
        db.flush()
        subscription = Subscription(
            user_id=user.id, plan_id=plan.id, status="active",
            starts_at=datetime.now(UTC) - timedelta(days=2),
            expires_at=datetime.now(UTC) - timedelta(minutes=1),
        )
        device = VpnDevice(
            user_id=user.id, node_id=node.id, device_name="Existing phone",
            xray_uuid="e42e2101-7516-474d-904c-62c3c36383a1",
            xray_email="expired-access-test@workplayvpn", is_active=True,
        )
        activation = DeviceActivation(
            user_id=user.id, location_id=location.id,
            token_hash=hashlib.sha256(RAW_TOKEN.encode()).hexdigest(),
            status="pending", expires_at=datetime.now(UTC) + timedelta(minutes=10),
        )
        db.add_all([subscription, device, activation])
        db.commit()
        yield subscription.id, device.id

    with SessionLocal() as db:
        db.execute(delete(User).where(User.telegram_id == TELEGRAM_ID))
        db.execute(delete(VpnNode).where(VpnNode.code == NODE_CODE))
        db.commit()


@pytest.mark.parametrize("entrypoint", ["device", "activation", "complete"])
def test_expired_access_revokes_existing_xray_device(
    expired_access, monkeypatch, entrypoint,
) -> None:
    subscription_id, device_id = expired_access
    removed = []
    monkeypatch.setattr(
        xray_node_service, "remove_device",
        lambda *, node, device: removed.append((node.code, device.id)),
    )

    with SessionLocal() as db, pytest.raises(HTTPException) as error:
        if entrypoint == "device":
            vpn_device_service.create_device(db, TELEGRAM_ID, NODE_CODE, "New phone")
        elif entrypoint == "activation":
            device_activation_service.create_activation(db, TELEGRAM_ID, "NL")
        else:
            device_activation_service.complete_activation(db, RAW_TOKEN, "New phone")

    assert error.value.status_code == 403
    assert removed == [(NODE_CODE, device_id)]
    with SessionLocal() as db:
        assert db.get(Subscription, subscription_id).status == "expired"


def test_failed_xray_revoke_leaves_subscription_for_worker_retry(
    expired_access, monkeypatch,
) -> None:
    subscription_id, _ = expired_access

    def unavailable(*, node, device):
        raise RuntimeError("node unavailable")

    monkeypatch.setattr(xray_node_service, "remove_device", unavailable)

    with SessionLocal() as db, pytest.raises(HTTPException) as error:
        vpn_device_service.create_device(db, TELEGRAM_ID, NODE_CODE, "New phone")

    assert error.value.status_code == 502
    with SessionLocal() as db:
        assert db.get(Subscription, subscription_id).status == "active"
