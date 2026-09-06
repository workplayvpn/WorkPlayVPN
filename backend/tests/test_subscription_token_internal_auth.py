import pytest
from fastapi.testclient import TestClient

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
