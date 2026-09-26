import hashlib
import hmac
import json
from datetime import UTC, datetime
from decimal import Decimal
from urllib.parse import urlencode

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.core.config import settings
from app.db.session import SessionLocal
from app.main import app
from app.models.user import User
from app.models.plan import Plan


TELEGRAM_ID = 993100004
IDEMPOTENCY_KEY = "mini-app-payment-request-0001"

client = TestClient(app)


def build_init_data() -> str:
    bot_token = settings.telegram_bot_token
    assert bot_token is not None

    fields = {
        "auth_date": str(
            int(datetime.now(UTC).timestamp())
        ),
        "query_id": "AAE-mini-app-payment-test",
        "user": json.dumps(
            {
                "id": TELEGRAM_ID,
                "first_name": "Payments",
                "username": "payments_test",
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


def remove_test_user() -> None:
    with SessionLocal() as database:
        database.execute(
            delete(User).where(
                User.telegram_id == TELEGRAM_ID
            )
        )
        database.commit()


@pytest.fixture(autouse=True)
def clean_test_user():
    remove_test_user()

    yield

    remove_test_user()


def test_payment_requires_telegram_credentials() -> None:
    response = client.post(
        "/mini-app/payments",
        json={
            "plan_code": "standard_7d",
            "idempotency_key": IDEMPOTENCY_KEY,
        },
    )

    assert response.status_code == 401


def test_mobile_payment_is_closed_outside_pilot(monkeypatch) -> None:
    code = "mobile_payment_pilot_test"
    monkeypatch.setattr(settings, "mobile_pilot_user_ids", "")
    with SessionLocal() as database:
        database.add(Plan(
            code=code, name="Mobile pilot", duration_days=30,
            price_amount=Decimal("249.00"), currency="RUB",
            access_tier="mobile", device_limit=3, is_active=True,
        ))
        database.commit()

    try:
        headers = {"X-Telegram-Init-Data": build_init_data()}
        assert client.get("/mini-app/me", headers=headers).status_code == 200
        payload = {"plan_code": code, "idempotency_key": "mobile-pilot-payment-test"}
        blocked = client.post("/mini-app/payments", headers=headers, json=payload)
        assert blocked.status_code == 404

        with SessionLocal() as database:
            user_id = database.query(User.id).filter(User.telegram_id == TELEGRAM_ID).scalar()
        monkeypatch.setattr(settings, "mobile_pilot_user_ids", str(user_id))
        allowed = client.post("/mini-app/payments", headers=headers, json=payload)
        assert allowed.status_code == 201
        assert allowed.json()["amount"] == "249.00"
    finally:
        remove_test_user()
        with SessionLocal() as database:
            database.execute(delete(Plan).where(Plan.code == code))
            database.commit()


def test_payment_is_created_once_for_repeated_request() -> None:
    headers = {
        "X-Telegram-Init-Data": build_init_data(),
    }

    profile_response = client.get(
        "/mini-app/me",
        headers=headers,
    )
    assert profile_response.status_code == 200

    payload = {
        "plan_code": "standard_7d",
        "idempotency_key": IDEMPOTENCY_KEY,
    }

    first_response = client.post(
        "/mini-app/payments",
        headers=headers,
        json=payload,
    )
    second_response = client.post(
        "/mini-app/payments",
        headers=headers,
        json=payload,
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 201
    assert second_response.json() == first_response.json()

    payment = first_response.json()

    assert payment["status"] == "pending"
    assert payment["amount"] == "99.00"
    assert payment["currency"] == "RUB"
    assert payment["confirmation_url"] is not None
    assert payment["expires_at"] is not None
    assert set(payment) == {
        "id",
        "status",
        "amount",
        "currency",
        "confirmation_url",
        "created_at",
        "expires_at",
        "paid_at",
    }


def test_trial_plan_cannot_be_purchased() -> None:
    headers = {
        "X-Telegram-Init-Data": build_init_data(),
    }

    profile_response = client.get(
        "/mini-app/me",
        headers=headers,
    )
    assert profile_response.status_code == 200

    response = client.post(
        "/mini-app/payments",
        headers=headers,
        json={
            "plan_code": "trial_1d",
            "idempotency_key": (
                "mini-app-trial-payment-request"
            ),
        },
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": "Trial plan does not require payment"
    }


def test_current_payment_can_be_resumed() -> None:
    headers = {
        "X-Telegram-Init-Data": build_init_data(),
    }

    profile_response = client.get(
        "/mini-app/me",
        headers=headers,
    )
    assert profile_response.status_code == 200

    empty_response = client.get(
        "/mini-app/payments/current",
        headers=headers,
    )

    assert empty_response.status_code == 200
    assert empty_response.json() is None

    create_response = client.post(
        "/mini-app/payments",
        headers=headers,
        json={
            "plan_code": "standard_1m",
            "idempotency_key": (
                "mini-app-resumable-payment-request"
            ),
        },
    )

    assert create_response.status_code == 201

    current_response = client.get(
        "/mini-app/payments/current",
        headers=headers,
    )

    assert current_response.status_code == 200
    assert current_response.json() == create_response.json()
