from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.api.subscription_tokens import build_token_response
from app.core.config import settings
from app.main import app


client = TestClient(app)

PROTECTED_PATHS = (
    "/subscription-tokens",
    "/subscription-tokens/rotate",
)

TEST_PAYLOAD = {
    "telegram_id": 987_654_321_012,
}


@pytest.mark.parametrize("path", PROTECTED_PATHS)
def test_subscription_token_endpoint_requires_credentials(
    path: str,
) -> None:
    response = client.post(
        path,
        json=TEST_PAYLOAD,
    )

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize("path", PROTECTED_PATHS)
def test_subscription_token_endpoint_rejects_wrong_credentials(
    path: str,
) -> None:
    response = client.post(
        path,
        json=TEST_PAYLOAD,
        headers={
            "Authorization": "Bearer wrong-internal-secret",
        },
    )

    assert response.status_code == 401


@pytest.mark.parametrize("path", PROTECTED_PATHS)
def test_subscription_token_endpoint_accepts_valid_credentials(
    path: str,
) -> None:
    response = client.post(
        path,
        json=TEST_PAYLOAD,
        headers={
            "Authorization": (
                f"Bearer {settings.internal_api_secret}"
            ),
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "User not found"


def test_build_token_response_includes_access_key() -> None:
    now = datetime.now(UTC)
    raw_token = "123.1.test-access-key"
    token = SimpleNamespace(
        created_at=now,
        rotated_at=None,
    )

    response = build_token_response(
        token=token,
        raw_token=raw_token,
    )

    assert response.access_key == raw_token
    assert response.subscription_url == (
        f"{settings.subscription_base_url.rstrip('/')}/"
        f"{raw_token}"
    )
    assert response.connect_url == (
        f"{settings.connect_base_url.rstrip('/')}/"
        f"{raw_token}"
    )
    assert response.created_at == now
    assert response.rotated_at is None


def test_device_token_links_match_mini_app_routes(monkeypatch):
    from unittest.mock import MagicMock
    from app.api import subscription_tokens as tokens
    now = datetime.now(UTC)
    token = SimpleNamespace(user_id=174, created_at=now, rotated_at=None)
    device = SimpleNamespace(id=7, mobile_xray_uuid="test", mobile_xray_email="test")
    database = MagicMock()
    database.scalars.return_value.all.return_value = [device]
    monkeypatch.setattr(tokens, "active_entitlements", lambda *args: {"basic": (), "mobile": ()})
    monkeypatch.setattr(tokens.subscription_token_service, "scoped_token", lambda *args: "mobile-token")
    monkeypatch.setattr(tokens, "auto_route_allowed", lambda user_id: True)
    result = tokens.build_token_response(token=token, raw_token="basic-token", database=database)
    assert result.basic_device_connect_urls["7"].endswith("/device/7/basic-token")
    assert result.mobile_device_connect_urls["7"].endswith("/auto/routed/device/7/mobile-token")
    assert result.mobile_subscription_url != result.subscription_url


def test_mobile_only_token_has_no_basic_device_links(monkeypatch):
    from unittest.mock import MagicMock
    from app.api import subscription_tokens as tokens
    token = SimpleNamespace(user_id=174, created_at=datetime.now(UTC), rotated_at=None)
    database = MagicMock()
    database.scalars.return_value.all.return_value = [SimpleNamespace(id=7, mobile_xray_uuid="test", mobile_xray_email="test")]
    monkeypatch.setattr(tokens, "active_entitlements", lambda *args: {"mobile": ()})
    monkeypatch.setattr(tokens.subscription_token_service, "scoped_token", lambda *args: "mobile-token")
    monkeypatch.setattr(tokens, "auto_route_allowed", lambda user_id: False)
    result = tokens.build_token_response(token=token, raw_token="basic-token", database=database)
    assert result.basic_device_connect_urls == {}
    assert result.subscription_url == result.mobile_subscription_url
    assert result.mobile_device_connect_urls["7"].endswith("/mobile-token")
