import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.core.config import settings
from app.db.session import SessionLocal
from app.main import app
from app.models.plan import Plan
from app.models.subscription import Subscription
from app.models.user import User


TELEGRAM_ID = 993100001
client = TestClient(app)


def build_init_data(
    *,
    first_name: str = "Nikita",
    username: str = "nikita_mini_app",
) -> str:
    bot_token = settings.telegram_bot_token
    assert bot_token is not None

    fields = {
        "auth_date": str(
            int(datetime.now(UTC).timestamp())
        ),
        "query_id": "AAE-mini-app-me-test",
        "user": json.dumps(
            {
                "id": TELEGRAM_ID,
                "first_name": first_name,
                "username": username,
                "language_code": "ru",
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


def test_me_requires_telegram_credentials() -> None:
    response = client.get("/mini-app/me")

    assert response.status_code == 401


def test_me_creates_user_from_signed_telegram_data() -> None:
    response = client.get(
        "/mini-app/me",
        headers={
            "X-Telegram-Init-Data": build_init_data(),
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "user": {
            "telegram_id": TELEGRAM_ID,
            "first_name": "Nikita",
            "username": "nikita_mini_app",
        },
        "subscription": None,
        "subscriptions": [],
        "connect_urls": {},
        "auto_connect_urls": {},
        "basic_device_connect_urls": {},
        "devices": {
            "active_count": 0,
            "total_limit": 0,
        },
        "current_region": None,
        "trial_available": True,
    }

    with SessionLocal() as database:
        user = database.scalar(
            select(User).where(
                User.telegram_id == TELEGRAM_ID
            )
        )

        assert user is not None
        assert user.first_name == "Nikita"
        assert user.username == "nikita_mini_app"


def test_me_updates_profile_from_new_signed_data() -> None:
    with SessionLocal() as database:
        database.add(
            User(
                telegram_id=TELEGRAM_ID,
                first_name="Old name",
                username="old_username",
            )
        )
        database.commit()

    response = client.get(
        "/mini-app/me",
        headers={
            "X-Telegram-Init-Data": build_init_data(
                first_name="Nikita Updated",
                username="new_username",
            ),
        },
    )

    assert response.status_code == 200
    assert response.json()["user"] == {
        "telegram_id": TELEGRAM_ID,
        "first_name": "Nikita Updated",
        "username": "new_username",
    }

    with SessionLocal() as database:
        user = database.scalar(
            select(User).where(
                User.telegram_id == TELEGRAM_ID
            )
        )

        assert user is not None
        assert user.first_name == "Nikita Updated"
        assert user.username == "new_username"


def test_trial_is_unavailable_with_active_paid_subscription() -> None:
    with SessionLocal() as database:
        plan = database.scalar(
            select(Plan).where(
                Plan.code == "standard_1m"
            )
        )
        assert plan is not None

        user = User(
            telegram_id=TELEGRAM_ID,
            first_name="Nikita",
            username="nikita_mini_app",
            is_active=True,
        )
        database.add(user)
        database.flush()

        now = datetime.now(UTC)
        database.add(
            Subscription(
                user_id=user.id,
                plan_id=plan.id,
                status="active",
                starts_at=now,
                expires_at=now + timedelta(days=30),
            )
        )
        database.commit()

    response = client.get(
        "/mini-app/me",
        headers={
            "X-Telegram-Init-Data": build_init_data(),
        },
    )

    assert response.status_code == 200
    assert response.json()["subscription"]["status"] == "active"
    assert response.json()["trial_available"] is False


def test_start_trial_requires_telegram_credentials() -> None:
    response = client.post("/mini-app/trial")

    assert response.status_code == 401


def test_start_trial_can_only_be_used_once() -> None:
    init_data = build_init_data()

    profile_response = client.get(
        "/mini-app/me",
        headers={
            "X-Telegram-Init-Data": init_data,
        },
    )
    assert profile_response.status_code == 200

    first_response = client.post(
        "/mini-app/trial",
        headers={
            "X-Telegram-Init-Data": init_data,
        },
    )

    assert first_response.status_code == 201

    subscription = first_response.json()
    assert subscription["status"] == "active"
    assert subscription["plan_code"] == "trial_1d"
    assert subscription["starts_at"] is not None
    assert subscription["expires_at"] is not None

    second_response = client.post(
        "/mini-app/trial",
        headers={
            "X-Telegram-Init-Data": init_data,
        },
    )

    assert second_response.status_code == 409
    assert second_response.json() == {
        "detail": "Trial already used"
    }

    refreshed_profile = client.get(
        "/mini-app/me",
        headers={
            "X-Telegram-Init-Data": init_data,
        },
    )

    assert refreshed_profile.status_code == 200
    assert refreshed_profile.json()["trial_available"] is False
    assert (
        refreshed_profile.json()["subscription"]["plan_code"]
        == "trial_1d"
    )
