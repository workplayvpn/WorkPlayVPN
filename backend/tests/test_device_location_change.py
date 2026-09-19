import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.core.config import settings
from app.db.session import SessionLocal
from app.main import app
from app.models.location import Location
from app.models.user import User
from app.models.vpn_device import VpnDevice
from app.models.vpn_node import VpnNode
from app.services.xray_node import xray_node_service


TELEGRAM_ID = 993100009
DEVICE_UUID = "12345678-1234-5678-1234-567812345679"
DEVICE_EMAIL = "region-change-test@workplayvpn"
SECOND_DEVICE_UUID = "12345678-1234-5678-1234-567812345680"
SECOND_DEVICE_EMAIL = "region-change-test-2@workplayvpn"
NL_NODE_CODE = "region-change-nl"
DE_NODE_CODE = "region-change-de"

client = TestClient(app)


def _clean_records() -> None:
    with SessionLocal() as database:
        database.execute(
            delete(User).where(User.telegram_id == TELEGRAM_ID)
        )
        database.execute(
            delete(VpnNode).where(
                VpnNode.code.in_({NL_NODE_CODE, DE_NODE_CODE})
            )
        )
        database.commit()


@pytest.fixture(autouse=True)
def isolated_records():
    _clean_records()
    yield
    _clean_records()


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.internal_api_secret}",
    }


def _create_device_with_two_nodes() -> tuple[int, int, int]:
    with SessionLocal() as database:
        nl = database.scalar(select(Location).where(Location.code == "NL"))
        de = database.scalar(select(Location).where(Location.code == "DE"))
        assert nl is not None
        assert de is not None

        user = User(
            telegram_id=TELEGRAM_ID,
            username="region_change_test",
            first_name="Region",
            is_active=True,
        )
        nl_node = VpnNode(
            location_id=nl.id,
            code=NL_NODE_CODE,
            name="Netherlands Test",
            host="192.0.2.20",
            ssh_port=22,
            ssh_user="test",
            is_active=True,
        )
        de_node = VpnNode(
            location_id=de.id,
            code=DE_NODE_CODE,
            name="Germany Test",
            host="192.0.2.21",
            ssh_port=22,
            ssh_user="test",
            is_active=True,
        )
        database.add_all([user, nl_node, de_node])
        database.flush()

        device = VpnDevice(
            user_id=user.id,
            node_id=nl_node.id,
            device_name="Region Test Phone",
            xray_uuid=DEVICE_UUID,
            xray_email=DEVICE_EMAIL,
            is_active=True,
        )
        database.add(device)
        database.commit()
        return device.id, nl_node.id, de_node.id


def test_change_device_location_keeps_credentials(monkeypatch) -> None:
    device_id, nl_node_id, de_node_id = _create_device_with_two_nodes()
    operations: list[tuple[str, str, str | None]] = []

    def fake_add_user(*, node, email, user_uuid=None):
        operations.append(("add", node.code, user_uuid))
        return user_uuid or DEVICE_UUID

    def fake_remove_user(*, node, email):
        operations.append(("remove", node.code, None))

    monkeypatch.setattr(xray_node_service, "add_user", fake_add_user)
    monkeypatch.setattr(xray_node_service, "remove_user", fake_remove_user)

    response = client.patch(
        f"/devices/{device_id}/location",
        headers=_headers(),
        json={
            "telegram_id": TELEGRAM_ID,
            "location_code": "DE",
        },
    )

    assert response.status_code == 200
    assert response.json()["node_code"] == DE_NODE_CODE
    assert operations == [
        ("add", DE_NODE_CODE, DEVICE_UUID),
        ("remove", NL_NODE_CODE, None),
    ]

    with SessionLocal() as database:
        device = database.get(VpnDevice, device_id)
        assert device is not None
        assert device.node_id == de_node_id
        assert device.node_id != nl_node_id
        assert device.xray_uuid == DEVICE_UUID
        assert device.xray_email == DEVICE_EMAIL


def test_change_device_location_moves_all_account_devices(
    monkeypatch,
) -> None:
    device_id, _, de_node_id = _create_device_with_two_nodes()

    with SessionLocal() as database:
        first_device = database.get(VpnDevice, device_id)
        assert first_device is not None

        second_device = VpnDevice(
            user_id=first_device.user_id,
            node_id=first_device.node_id,
            device_name="Region Test Laptop",
            xray_uuid=SECOND_DEVICE_UUID,
            xray_email=SECOND_DEVICE_EMAIL,
            is_active=True,
        )
        database.add(second_device)
        database.commit()
        second_device_id = second_device.id

    operations: list[tuple[str, str, str | None]] = []

    def fake_add_user(*, node, email, user_uuid=None):
        operations.append(("add", node.code, user_uuid))
        return user_uuid or DEVICE_UUID

    def fake_remove_user(*, node, email):
        operations.append(("remove", node.code, None))

    monkeypatch.setattr(xray_node_service, "add_user", fake_add_user)
    monkeypatch.setattr(xray_node_service, "remove_user", fake_remove_user)

    response = client.patch(
        f"/devices/{device_id}/location",
        headers=_headers(),
        json={
            "telegram_id": TELEGRAM_ID,
            "location_code": "DE",
        },
    )

    assert response.status_code == 200
    assert operations == [
        ("add", DE_NODE_CODE, DEVICE_UUID),
        ("add", DE_NODE_CODE, SECOND_DEVICE_UUID),
        ("remove", NL_NODE_CODE, None),
        ("remove", NL_NODE_CODE, None),
    ]

    with SessionLocal() as database:
        devices = database.scalars(
            select(VpnDevice).where(
                VpnDevice.id.in_({device_id, second_device_id})
            )
        ).all()
        user = database.scalar(
            select(User).where(User.telegram_id == TELEGRAM_ID)
        )

        assert len(devices) == 2
        assert {device.node_id for device in devices} == {de_node_id}
        assert user is not None
        assert user.preferred_location_id is not None


def test_change_device_location_rejects_unowned_device(monkeypatch) -> None:
    device_id, _, _ = _create_device_with_two_nodes()
    monkeypatch.setattr(
        xray_node_service,
        "add_user",
        lambda **kwargs: DEVICE_UUID,
    )

    response = client.patch(
        f"/devices/{device_id}/location",
        headers=_headers(),
        json={
            "telegram_id": TELEGRAM_ID + 1,
            "location_code": "DE",
        },
    )

    assert response.status_code == 404
