import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta
from urllib.parse import quote, urlencode, urlsplit

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.core.config import settings
from app.api import happ_auto_route as auto_route_api
from app.db.session import SessionLocal
from app.main import app
from app.models.location import Location
from app.models.plan import Plan
from app.models.subscription import Subscription
from app.models.user import User
from app.models.vpn_device import VpnDevice
from app.models.vpn_node import VpnNode
from app.services.xray_node import xray_node_service


TELEGRAM_ID = 993100003
NODE_CODE = "mini-app-test-node"
SECOND_NODE_CODE = "mini-app-test-node-de"
DEVICE_UUID = "12345678-1234-5678-1234-567812345678"
CLIENT_INSTANCE_ID = "9d6922e5-080b-4a20-a684-35e11e15df8d"

client = TestClient(app)


def build_init_data() -> str:
    bot_token = settings.telegram_bot_token
    assert bot_token is not None

    fields = {
        "auth_date": str(
            int(datetime.now(UTC).timestamp())
        ),
        "query_id": "AAE-mini-app-devices-test",
        "user": json.dumps(
            {
                "id": TELEGRAM_ID,
                "first_name": "Devices",
                "username": "devices_test",
            },
            separators=(",", ":"),
        ),
    }
    data_check_string = "\n".join(
        f"{key}={value}"
        for key, value in sorted(fields.items())
    )
    secret_key = hmac.new(
        b"WebAppData",
        bot_token.encode(),
        hashlib.sha256,
    ).digest()
    fields["hash"] = hmac.new(
        secret_key,
        data_check_string.encode(),
        hashlib.sha256,
    ).hexdigest()

    return urlencode(fields)


def clean_records() -> None:
    with SessionLocal() as database:
        database.execute(
            delete(User).where(
                User.telegram_id == TELEGRAM_ID
            )
        )
        database.execute(
            delete(VpnNode).where(
                VpnNode.code.in_({
                    NODE_CODE,
                    SECOND_NODE_CODE,
                })
            )
        )
        database.commit()


@pytest.fixture(autouse=True)
def isolated_records():
    clean_records()

    with SessionLocal() as database:
        location = database.scalar(
            select(Location).where(Location.code == "NL")
        )
        assert location is not None

        database.add(
            VpnNode(
                location_id=location.id,
                code=NODE_CODE,
                name="Mini App Test Node",
                host="192.0.2.10",
                ssh_port=22,
                ssh_user="test",
                is_active=True,
            )
        )
        database.commit()

    yield

    clean_records()


def test_device_routes_require_telegram_credentials() -> None:
    assert client.get(
        "/mini-app/devices"
    ).status_code == 401

    assert client.post(
        "/mini-app/devices",
        json={
            "device_name": "iPhone (iOS)",
            "platform": "iOS",
            "client_instance_id": CLIENT_INSTANCE_ID,
        },
    ).status_code == 401

    assert client.post(
        "/mini-app/device-activations",
        json={
            "location_code": "NL",
        },
    ).status_code == 401

    assert client.delete(
        "/mini-app/devices/1"
    ).status_code == 401


def test_auto_ru_link_requires_pilot_mobile_and_provisioned_device(monkeypatch) -> None:
    headers = {"X-Telegram-Init-Data": build_init_data()}
    assert client.get("/mini-app/me", headers=headers).status_code == 200
    with SessionLocal() as database:
        user = database.scalar(select(User).where(User.telegram_id == TELEGRAM_ID))
        node = database.scalar(select(VpnNode).where(VpnNode.code == NODE_CODE))
        plan = database.scalar(select(Plan).where(Plan.code == "mobile_1m"))
        assert user and node and plan
        now = datetime.now(UTC)
        database.add(Subscription(
            user_id=user.id, plan_id=plan.id, status="active",
            starts_at=now, expires_at=now + timedelta(days=30),
        ))
        device = VpnDevice(
            user_id=user.id, node_id=node.id, device_name="Pilot",
            xray_uuid=DEVICE_UUID, xray_email="auto-test@workplayvpn",
            is_active=True,
        )
        database.add(device)
        database.commit()
        user_id = user.id
        device_id = device.id

    monkeypatch.setattr(settings, "happ_auto_route_user_ids", "")
    profile = client.get("/mini-app/me", headers=headers).json()
    urls = profile["connect_urls"]
    assert "mobile" in urls and "mobile_auto_ru" not in urls
    assert profile["auto_connect_urls"] == {}

    monkeypatch.setattr(settings, "happ_auto_route_user_ids", str(user_id))
    profile = client.get("/mini-app/me", headers=headers).json()
    urls = profile["connect_urls"]
    assert "mobile_auto_ru" not in urls
    assert profile["auto_connect_urls"] == {}

    with SessionLocal() as database:
        device = database.get(VpnDevice, device_id)
        device.mobile_xray_uuid = "33333333-4444-4555-8666-777777777777"
        device.mobile_xray_email = "mobile_auto-test@workplayvpn"
        second = VpnDevice(
            user_id=user_id, node_id=device.node_id, device_name="Second",
            xray_uuid="44444444-5555-4666-8777-888888888888",
            xray_email="auto-test-2@workplayvpn", is_active=True,
            mobile_xray_uuid="55555555-6666-4777-8888-999999999999",
            mobile_xray_email="mobile_auto-test-2@workplayvpn",
        )
        database.add(second)
        database.commit()
        second_id = second.id

    profile = client.get("/mini-app/me", headers=headers).json()
    urls = profile["connect_urls"]
    assert "mobile_auto_ru" not in urls
    assert urls["mobile"].startswith(
        f"{settings.connect_base_url.rstrip('/')}/auto/routed/device/"
    )
    assert ".mobile." in urls["mobile"]
    auto_urls = profile["auto_connect_urls"]
    assert set(auto_urls) == {str(device_id), str(second_id)}
    assert f"/device/{device_id}/" in auto_urls[str(device_id)]
    assert f"/device/{second_id}/" in auto_urls[str(second_id)]
    assert auto_urls[str(device_id)] != auto_urls[str(second_id)]
    assert urls["mobile"] == auto_urls[str(device_id)]

    def build_links(*, device, **kwargs):
        return [
            f"vless://{device.xray_uuid}@direct.example:443?" + urlencode({
            "type": "tcp", "security": "reality", "sni": "cover.example",
            "pbk": "public-key", "fp": "chrome",
        }) + "#" + quote("🇳🇱 Нидерланды — Wi-Fi", safe=""),
            f"vless://{device.mobile_xray_uuid}@cdn.example:443?" + urlencode({
                "type": "xhttp", "security": "tls", "sni": "cdn.example",
                "path": "/relay/",
            }),
        ]

    monkeypatch.setattr(
        auto_route_api.vpn_node_profile_service,
        "get_active_profiles_for_nodes", lambda **kwargs: ["ready"],
    )
    monkeypatch.setattr(auto_route_api.subscription_builder, "build", build_links)
    for item_id, direct_uuid, mobile_uuid in (
        (device_id, DEVICE_UUID, "33333333-4444-4555-8666-777777777777"),
        (second_id, "44444444-5555-4666-8777-888888888888",
         "55555555-6666-4777-8888-999999999999"),
    ):
        page = urlsplit(auto_urls[str(item_id)]).path
        assert client.get(page).status_code == 200
        response = client.get(page.replace("/connect/happ/", "/sub/"))
        assert response.status_code == 200
        assert response.headers["profile-title"] == "Work&PlayVPN Mobile"
        config = response.json()[0]
        assert config["outbounds"][0]["settings"]["vnext"][0]["users"][0]["id"] == direct_uuid
        assert config["outbounds"][1]["settings"]["vnext"][0]["users"][0]["id"] == mobile_uuid
        assert config["remarks"] == f"🇳🇱 Нидерланды · WP-{item_id:06d}"

    unknown_page = urlsplit(auto_urls[str(device_id)]).path.replace(
        f"/device/{device_id}/", "/device/999999/",
    )
    assert client.get(unknown_page).status_code == 404
    assert client.get(unknown_page.replace("/connect/happ/", "/sub/")).status_code == 404

    with SessionLocal() as database:
        database.get(VpnDevice, second_id).is_active = False
        database.commit()
    profile = client.get("/mini-app/me", headers=headers).json()
    assert set(profile["auto_connect_urls"]) == {str(device_id)}
    removed_page = urlsplit(auto_urls[str(second_id)]).path
    assert client.get(removed_page).status_code == 404
    assert client.get(removed_page.replace("/connect/happ/", "/sub/")).status_code == 404


def test_activation_rejects_location_without_active_node() -> None:
    headers = {
        "X-Telegram-Init-Data": build_init_data(),
    }

    catalog_response = client.get(
        "/mini-app/catalog",
        headers=headers,
    )
    assert catalog_response.status_code == 200

    locations = {
        location["code"]: location
        for location in catalog_response.json()["locations"]
    }
    assert locations["NL"]["available"] is True
    assert locations["DE"]["available"] is False

    profile_response = client.get(
        "/mini-app/me",
        headers=headers,
    )
    assert profile_response.status_code == 200

    trial_response = client.post(
        "/mini-app/trial",
        headers=headers,
    )
    assert trial_response.status_code == 201

    response = client.post(
        "/mini-app/device-activations",
        headers=headers,
        json={
            "location_code": "DE",
        },
    )

    assert response.status_code == 503
    assert response.json() == {
        "detail": "VPN node unavailable"
    }


def test_device_lifecycle_uses_signed_user(
    monkeypatch,
) -> None:
    added_users: list[tuple[str, str]] = []
    removed_users: list[tuple[str, str]] = []

    def fake_add_user(*, node, email, user_uuid=None):
        added_users.append((node.code, email))
        return user_uuid or DEVICE_UUID

    def fake_remove_user(*, node, email):
        removed_users.append((node.code, email))

    monkeypatch.setattr(
        xray_node_service,
        "add_user",
        fake_add_user,
    )
    monkeypatch.setattr(
        xray_node_service,
        "remove_user",
        fake_remove_user,
    )

    init_data = build_init_data()
    headers = {
        "X-Telegram-Init-Data": init_data,
    }

    profile_response = client.get(
        "/mini-app/me",
        headers=headers,
    )
    assert profile_response.status_code == 200

    trial_response = client.post(
        "/mini-app/trial",
        headers=headers,
    )
    assert trial_response.status_code == 201

    activation_response = client.post(
        "/mini-app/device-activations",
        headers=headers,
        json={
            "location_code": "NL",
        },
    )

    assert activation_response.status_code == 201
    activation = activation_response.json()
    assert set(activation) == {
        "activation_id",
        "expires_at",
        "activation_url",
    }
    assert activation["activation_url"].startswith(
        settings.activation_base_url
    )

    raw_token = activation["activation_url"].rsplit("/", 1)[-1]

    complete_response = client.post(
        f"/device-activations/{raw_token}/complete",
        json={
            "device_name": "iPhone 17 Pro Max",
            "platform": "ios",
        },
    )

    assert complete_response.status_code == 200
    completed_device = complete_response.json()
    assert completed_device["device_name"] == "iPhone 17 Pro Max"
    assert completed_device["node_code"] == NODE_CODE
    assert completed_device["node_name"] == "Mini App Test Node"
    assert len(added_users) == 1
    assert added_users[0][0] == NODE_CODE

    list_response = client.get(
        "/mini-app/devices",
        headers=headers,
    )

    assert list_response.status_code == 200
    devices = list_response.json()
    assert len(devices) == 1

    created_device = devices[0]
    assert created_device["device_name"] == "iPhone 17 Pro Max"
    assert created_device["node_code"] == NODE_CODE
    assert created_device["node_name"] == "Mini App Test Node"
    assert created_device["is_active"] is True
    assert set(created_device) == {
        "id",
        "device_name",
        "node_code",
        "node_name",
        "is_active",
        "created_at",
    }

    delete_response = client.delete(
        f"/mini-app/devices/{created_device['id']}",
        headers=headers,
    )

    assert delete_response.status_code == 204
    assert delete_response.content == b""
    assert len(removed_users) == 1
    assert removed_users[0][0] == NODE_CODE

    empty_list_response = client.get(
        "/mini-app/devices",
        headers=headers,
    )

    assert empty_list_response.status_code == 200
    assert empty_list_response.json() == []


def test_device_can_be_created_inside_mini_app(
    monkeypatch,
) -> None:
    added_users: list[tuple[str, str]] = []

    def fake_add_user(*, node, email, user_uuid=None):
        added_users.append((node.code, email))
        return user_uuid or DEVICE_UUID

    monkeypatch.setattr(
        xray_node_service,
        "add_user",
        fake_add_user,
    )

    headers = {
        "X-Telegram-Init-Data": build_init_data(),
    }

    assert client.get(
        "/mini-app/me",
        headers=headers,
    ).status_code == 200

    assert client.post(
        "/mini-app/trial",
        headers=headers,
    ).status_code == 201

    response = client.post(
        "/mini-app/devices",
        headers=headers,
        json={
            "device_name": "iPhone (iOS)",
            "platform": "iOS",
            "client_instance_id": CLIENT_INSTANCE_ID,
        },
    )

    assert response.status_code == 201
    created_device = response.json()
    assert created_device["connect_url"].startswith(
        settings.connect_base_url
    )
    assert created_device["mobile_connect_url"] is None

    device = {
        key: value
        for key, value in created_device.items()
        if key not in {"connect_url", "mobile_connect_url"}
    }
    assert device["device_name"] == "iPhone (iOS)"
    assert device["node_code"] == NODE_CODE
    assert device["node_name"] == "Mini App Test Node"
    assert device["is_active"] is True
    assert len(added_users) == 1

    repeated_response = client.post(
        "/mini-app/devices",
        headers=headers,
        json={
            "device_name": "iPhone 2 (iOS)",
            "platform": "iOS",
            "client_instance_id": CLIENT_INSTANCE_ID,
        },
    )

    assert repeated_response.status_code == 201
    assert repeated_response.json() == created_device
    assert len(added_users) == 1

    devices_response = client.get(
        "/mini-app/devices",
        headers=headers,
    )

    assert devices_response.status_code == 200
    assert devices_response.json() == [device]


def test_device_creation_requires_valid_client_instance_id() -> None:
    headers = {
        "X-Telegram-Init-Data": build_init_data(),
    }

    assert client.get(
        "/mini-app/me",
        headers=headers,
    ).status_code == 200

    response = client.post(
        "/mini-app/devices",
        headers=headers,
        json={
            "device_name": "iPhone (iOS)",
            "platform": "iOS",
            "client_instance_id": "too short!",
        },
    )

    assert response.status_code == 422


def test_region_change_moves_all_mini_app_devices(
    monkeypatch,
) -> None:
    operations: list[tuple[str, str, str | None]] = []

    def fake_add_user(*, node, email, user_uuid=None):
        operations.append(("add", node.code, user_uuid))
        return user_uuid or DEVICE_UUID

    def fake_remove_user(*, node, email):
        operations.append(("remove", node.code, None))

    monkeypatch.setattr(
        xray_node_service,
        "add_user",
        fake_add_user,
    )
    monkeypatch.setattr(
        xray_node_service,
        "remove_user",
        fake_remove_user,
    )

    headers = {
        "X-Telegram-Init-Data": build_init_data(),
    }

    assert client.get(
        "/mini-app/me",
        headers=headers,
    ).status_code == 200
    assert client.post(
        "/mini-app/trial",
        headers=headers,
    ).status_code == 201

    create_response = client.post(
        "/mini-app/devices",
        headers=headers,
        json={
            "device_name": "iPhone (iOS)",
            "platform": "iOS",
            "client_instance_id": CLIENT_INSTANCE_ID,
        },
    )
    assert create_response.status_code == 201

    with SessionLocal() as database:
        germany = database.scalar(
            select(Location).where(Location.code == "DE")
        )
        assert germany is not None

        database.add(
            VpnNode(
                location_id=germany.id,
                code=SECOND_NODE_CODE,
                name="Mini App Germany Test Node",
                host="192.0.2.11",
                ssh_port=22,
                ssh_user="test",
                is_active=True,
            )
        )
        database.commit()

    operations.clear()
    region_response = client.patch(
        "/mini-app/region",
        headers=headers,
        json={"location_code": "DE"},
    )

    assert region_response.status_code == 200
    assert region_response.json() == {
        "code": "DE",
        "name": "Германия",
    }
    assert operations == [
        ("add", SECOND_NODE_CODE, DEVICE_UUID),
        ("remove", NODE_CODE, None),
    ]

    me_response = client.get(
        "/mini-app/me",
        headers=headers,
    )
    assert me_response.status_code == 200
    assert me_response.json()["current_region"] == {
        "code": "DE",
        "name": "Германия",
    }

    with SessionLocal() as database:
        user = database.scalar(
            select(User).where(User.telegram_id == TELEGRAM_ID)
        )
        assert user is not None

        device = database.scalar(
            select(VpnDevice).where(VpnDevice.user_id == user.id)
        )
        target_node = database.scalar(
            select(VpnNode).where(VpnNode.code == SECOND_NODE_CODE)
        )

        assert device is not None
        assert target_node is not None
        assert user.preferred_location_id == target_node.location_id
        assert device.node_id == target_node.id
