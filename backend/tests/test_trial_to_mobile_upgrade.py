from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import delete, select

from app.db.session import SessionLocal
from app.models.location import Location
from app.models.plan import Plan
from app.models.subscription import Subscription
from app.models.user import User
from app.models.vpn_device import VpnDevice
from app.models.vpn_node import VpnNode
from app.services import subscription_service as subscription_module
from app.services.subscription_service import subscription_service
from app.services.xray_node import xray_node_service


@pytest.fixture
def trial_upgrade(monkeypatch):
    monkeypatch.setattr(subscription_module, "require_mobile_profile", lambda db, node_id: None)
    with SessionLocal() as database:
        database.execute(delete(User).where(User.telegram_id == 993100030))
        database.execute(delete(VpnNode).where(VpnNode.code == "upgrade-test-node"))
        database.commit()
        location = database.scalar(select(Location).where(Location.code == "NL"))
        trial = database.scalar(select(Plan).where(Plan.code == "trial_1d"))
        mobile = database.scalar(select(Plan).where(Plan.code == "mobile_1m"))
        assert location is not None and trial is not None and mobile is not None

        user = User(telegram_id=993100030, first_name="Upgrade test")
        node = VpnNode(
            location_id=location.id, code="upgrade-test-node", name="Upgrade test",
            host="192.0.2.30", ssh_user="test", is_active=True,
        )
        database.add_all([user, node])
        database.flush()
        expires_at = datetime.now(UTC) + timedelta(hours=20)
        existing = Subscription(
            user_id=user.id, plan_id=trial.id, status="active",
            starts_at=datetime.now(UTC), expires_at=expires_at,
        )
        purchase = Subscription(user_id=user.id, plan_id=mobile.id, status="pending")
        device = VpnDevice(
            user_id=user.id, node_id=node.id, device_name="iPhone",
            xray_uuid="e42e2101-7516-474d-904c-62c3c36383a2",
            xray_email="upgrade-test@workplayvpn", is_active=True,
        )
        database.add_all([existing, purchase, device])
        database.commit()
        yield database, existing.id, purchase.id, device.id, expires_at
        database.execute(delete(User).where(User.telegram_id == 993100030))
        database.execute(delete(VpnNode).where(VpnNode.code == "upgrade-test-node"))
        database.commit()


def test_trial_to_mobile_adds_only_mobile_and_preserves_trial_time(
    trial_upgrade, monkeypatch,
) -> None:
    database, trial_id, purchase_id, device_id, expires_at = trial_upgrade
    added, removed = [], []
    monkeypatch.setattr(
        xray_node_service, "add_mobile_user",
        lambda node, email, user_uuid: added.append((email, user_uuid)),
    )
    monkeypatch.setattr(
        xray_node_service, "remove_mobile_user",
        lambda node, email: removed.append(email),
    )
    result = subscription_service.activate_subscription(
        database, database.get(Subscription, purchase_id),
    )
    device = database.get(VpnDevice, device_id)
    assert result.id == trial_id
    assert result.expires_at == expires_at + timedelta(days=30)
    assert database.get(Subscription, purchase_id).status == "applied"
    assert database.get(Plan, result.plan_id).code == "mobile_1m"
    assert device.mobile_xray_uuid and device.mobile_xray_email
    assert added == [(device.mobile_xray_email, device.mobile_xray_uuid)]
    assert removed == []

    subscription_service.activate_subscription(
        database, database.get(Subscription, purchase_id),
    )
    assert len(added) == 1
    assert database.get(Subscription, trial_id).expires_at == expires_at + timedelta(days=30)


def test_trial_to_mobile_provision_failure_keeps_trial(
    trial_upgrade, monkeypatch,
) -> None:
    database, trial_id, purchase_id, device_id, expires_at = trial_upgrade

    def fail(node, email, user_uuid):
        raise RuntimeError("CDN unavailable")

    monkeypatch.setattr(xray_node_service, "add_mobile_user", fail)
    with pytest.raises(RuntimeError, match="CDN unavailable"):
        subscription_service.activate_subscription(
            database, database.get(Subscription, purchase_id),
        )

    database.expire_all()
    trial = database.get(Subscription, trial_id)
    assert trial.status == "active"
    assert trial.expires_at == expires_at
    assert database.get(Subscription, purchase_id).status == "pending"
    assert database.get(VpnDevice, device_id).mobile_xray_uuid is None
