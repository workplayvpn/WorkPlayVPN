import hashlib
import hmac
import json
from datetime import UTC, datetime
from urllib.parse import urlencode

from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app


client = TestClient(app)


def build_init_data() -> str:
    bot_token = settings.telegram_bot_token
    assert bot_token is not None

    fields = {
        "auth_date": str(
            int(datetime.now(UTC).timestamp())
        ),
        "query_id": "AAE-mini-app-catalog-test",
        "user": json.dumps(
            {
                "id": 993100002,
                "first_name": "Catalog",
                "username": "catalog_test",
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


def test_catalog_requires_telegram_credentials() -> None:
    response = client.get("/mini-app/catalog")

    assert response.status_code == 401


def test_catalog_returns_current_paid_plans() -> None:
    response = client.get(
        "/mini-app/catalog",
        headers={
            "X-Telegram-Init-Data": build_init_data(),
        },
    )

    assert response.status_code == 200

    payload = response.json()
    plans = payload["plans"]

    assert [
        (
            plan["code"],
            plan["duration_days"],
            plan["price_amount"],
            plan["device_limit"],
        )
        for plan in plans
    ] == [
        ("standard_7d", 7, "99.00", 3),
        ("standard_1m", 30, "199.00", 3),
        ("standard_3m", 90, "499.00", 3),
        ("standard_6m", 180, "899.00", 3),
        ("standard_12m", 365, "1599.00", 3),
    ]

    assert all(
        set(plan) == {
            "code",
            "name",
            "duration_days",
            "price_amount",
            "currency",
            "device_limit",
        }
        for plan in plans
    )

    assert all(
        set(location) == {
            "code",
            "name",
        }
        for location in payload["locations"]
    )
