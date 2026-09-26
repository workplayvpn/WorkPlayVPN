import hashlib
import hmac
import json
from datetime import UTC, datetime
from decimal import Decimal
from urllib.parse import urlencode

from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.core.config import settings
from app.db.session import SessionLocal
from app.main import app
from app.models.plan import Plan


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
            "access_tier",
        }
        for plan in plans
    )

    assert all(
        set(location) == {
            "code",
            "name",
            "available",
        }
        for location in payload["locations"]
    )

    assert all(
        isinstance(location["available"], bool)
        for location in payload["locations"]
    )

    assert all(plan["access_tier"] == "basic" for plan in plans)


def test_catalog_exposes_active_mobile_plans_separately() -> None:
    code = "mobile_catalog_test"
    with SessionLocal() as db:
        db.add(Plan(
            code=code, name="Mobile test", duration_days=30,
            price_amount=Decimal("299.00"), currency="RUB",
            access_tier="mobile", device_limit=1, is_active=True,
        ))
        db.commit()

    try:
        response = client.get(
            "/mini-app/catalog",
            headers={"X-Telegram-Init-Data": build_init_data()},
        )
        assert response.status_code == 200
        mobile_plans = [
            plan for plan in response.json()["plans"]
            if plan["access_tier"] == "mobile"
        ]
        assert len(mobile_plans) == 1
        assert mobile_plans[0]["code"] == code
        assert mobile_plans[0]["price_amount"] == "299.00"
    finally:
        with SessionLocal() as db:
            db.execute(delete(Plan).where(Plan.code == code))
            db.commit()
