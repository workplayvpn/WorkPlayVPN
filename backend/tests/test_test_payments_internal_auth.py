from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app


client = TestClient(app)

TEST_PAYMENT_PATH = (
    "/test/payments/2147483647/succeed"
)


def test_test_payment_endpoint_requires_credentials() -> None:
    response = client.post(
        TEST_PAYMENT_PATH,
    )

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_test_payment_endpoint_rejects_wrong_credentials() -> None:
    response = client.post(
        TEST_PAYMENT_PATH,
        headers={
            "Authorization": "Bearer wrong-internal-secret",
        },
    )

    assert response.status_code == 401


def test_test_payment_endpoint_accepts_valid_credentials() -> None:
    response = client.post(
        TEST_PAYMENT_PATH,
        headers={
            "Authorization": (
                f"Bearer {settings.internal_api_secret}"
            ),
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Payment not found"