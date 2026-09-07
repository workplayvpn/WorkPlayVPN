import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app


client = TestClient(app)

INTERNAL_REQUESTS = (
    ("post", "/users", {}),
    ("get", "/users/987654321012", None),
    ("post", "/subscriptions", {}),
    (
        "get",
        "/subscriptions/users/987654321012/current",
        None,
    ),
    ("post", "/devices", {}),
    ("get", "/devices/users/987654321012", None),
    (
        "delete",
        "/devices/2147483647?telegram_id=987654321012",
        None,
    ),
    ("post", "/payments", {}),
    ("post", "/payments/2147483647/cancel", {}),
    ("post", "/device-activations", {}),
)


def send_request(
    method: str,
    path: str,
    *,
    headers: dict[str, str] | None = None,
    payload: dict | None = None,
):
    return client.request(
        method,
        path,
        headers=headers,
        json=payload,
    )


@pytest.mark.parametrize(
    ("method", "path", "payload"),
    INTERNAL_REQUESTS,
)
def test_internal_route_requires_credentials(
    method: str,
    path: str,
    payload: dict | None,
) -> None:
    response = send_request(
        method,
        path,
        payload=payload,
    )

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize(
    ("method", "path", "payload"),
    INTERNAL_REQUESTS,
)
def test_internal_route_rejects_wrong_credentials(
    method: str,
    path: str,
    payload: dict | None,
) -> None:
    response = send_request(
        method,
        path,
        headers={
            "Authorization": "Bearer wrong-internal-secret",
        },
        payload=payload,
    )

    assert response.status_code == 401


@pytest.mark.parametrize(
    ("method", "path", "payload"),
    INTERNAL_REQUESTS,
)
def test_internal_route_accepts_valid_credentials(
    method: str,
    path: str,
    payload: dict | None,
) -> None:
    response = send_request(
        method,
        path,
        headers={
            "Authorization": (
                f"Bearer {settings.internal_api_secret}"
            ),
        },
        payload=payload,
    )

    assert response.status_code != 401


def test_device_activation_completion_remains_public() -> None:
    response = client.post(
        "/device-activations/invalid-token/complete",
        json={},
    )

    assert response.status_code != 401