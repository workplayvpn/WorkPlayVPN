import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.core.config import settings
from app.db.session import SessionLocal
from app.main import app
from app.models.vpn_node import VpnNode
from app.models.vpn_node_profile import VpnNodeProfile


client = TestClient(app)


TEST_NODE_CODE = "nl-mobile-readiness-test"
TEST_PROFILE_CODE = "nl-mobile-readiness-profile"


def cleanup_mobile_readiness_test_data() -> None:
    with SessionLocal() as database:
        database.execute(
            delete(VpnNodeProfile).where(
                VpnNodeProfile.code == TEST_PROFILE_CODE
            )
        )
        database.execute(
            delete(VpnNode).where(
                VpnNode.code == TEST_NODE_CODE
            )
        )
        database.commit()


@pytest.fixture(autouse=True)
def isolated_mobile_readiness_data():
    cleanup_mobile_readiness_test_data()

    yield

    cleanup_mobile_readiness_test_data()


def auth_headers() -> dict[str, str]:
    return {
        "Authorization": (
            f"Bearer {settings.internal_api_secret}"
        ),
    }


def create_node(
    *,
    is_active: bool = True,
) -> VpnNode:
    with SessionLocal() as database:
        node = VpnNode(
            location_id=1,
            code=TEST_NODE_CODE,
            name="NL Mobile Readiness Test",
            host="nl-test.workplayvpn.local",
            ssh_port=22,
            ssh_user="test",
            is_active=is_active,
        )

        database.add(node)
        database.commit()
        database.refresh(node)

        database.expunge(node)

        return node


def create_mobile_profile(
    *,
    node_id: int,
    is_active: bool,
    server_address: str = "mobile.workplayvpn.local",
    path: str = "/mobile",
) -> VpnNodeProfile:
    with SessionLocal() as database:
        profile = VpnNodeProfile(
            node_id=node_id,
            code=TEST_PROFILE_CODE,
            name="NL Mobile Readiness Profile",
            protocol="vless",
            network="xhttp",
            security="tls",
            port=443,
            flow=None,
            server_name="mobile.workplayvpn.local",
            settings={
                "happ_access_mode": "mobile",
                "happ_server_address": server_address,
                "path": path,
                "mode": "auto",
            },
            is_active=is_active,
        )

        database.add(profile)
        database.commit()
        database.refresh(profile)

        database.expunge(profile)

        return profile


def test_mobile_readiness_requires_internal_auth() -> None:
    response = client.get(
        "/internal/happ/mobile-readiness"
    )

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_mobile_readiness_reports_missing_profile() -> None:
    response = client.get(
        "/internal/happ/mobile-readiness",
        headers=auth_headers(),
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload == {
        "status": "not_ready",
        "mobile_profile_found": False,
        "profile_active": False,
        "node_active": False,
        "configuration_valid": False,
        "issues": [
            "mobile_profile_missing",
        ],
    }


def test_mobile_readiness_reports_inactive_valid_profile() -> None:
    node = create_node()

    create_mobile_profile(
        node_id=node.id,
        is_active=False,
    )

    response = client.get(
        "/internal/happ/mobile-readiness",
        headers=auth_headers(),
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["status"] == "not_ready"
    assert payload["mobile_profile_found"] is True
    assert payload["profile_active"] is False
    assert payload["node_active"] is True
    assert payload["configuration_valid"] is True
    assert "profile_inactive" in payload["issues"]


def test_mobile_readiness_reports_invalid_configuration() -> None:
    node = create_node()

    create_mobile_profile(
        node_id=node.id,
        is_active=True,
        server_address="https://mobile.workplayvpn.local",
    )

    response = client.get(
        "/internal/happ/mobile-readiness",
        headers=auth_headers(),
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["status"] == "not_ready"
    assert payload["mobile_profile_found"] is True
    assert payload["profile_active"] is True
    assert payload["node_active"] is True
    assert payload["configuration_valid"] is False
    assert "configuration_invalid" in payload["issues"]


def test_mobile_readiness_reports_inactive_node() -> None:
    node = create_node(
        is_active=False,
    )

    create_mobile_profile(
        node_id=node.id,
        is_active=True,
    )

    response = client.get(
        "/internal/happ/mobile-readiness",
        headers=auth_headers(),
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["status"] == "not_ready"
    assert payload["mobile_profile_found"] is True
    assert payload["profile_active"] is True
    assert payload["node_active"] is False
    assert payload["configuration_valid"] is True
    assert "node_inactive" in payload["issues"]


def test_mobile_readiness_reports_ready_profile() -> None:
    node = create_node()

    create_mobile_profile(
        node_id=node.id,
        is_active=True,
    )

    response = client.get(
        "/internal/happ/mobile-readiness",
        headers=auth_headers(),
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload == {
        "status": "ready",
        "mobile_profile_found": True,
        "profile_active": True,
        "node_active": True,
        "configuration_valid": True,
        "issues": [],
    }