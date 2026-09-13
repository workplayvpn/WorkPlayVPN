from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.core.config import settings
from app.db.session import SessionLocal
from app.main import app
from app.models.plan import Plan
from app.models.subscription import Subscription
from app.models.user import User
from app.services.subscription_token_service import (
    subscription_token_service,
)


client = TestClient(app)

TEST_TELEGRAM_IDS = (996000001, 996000002)


def remove_test_users() -> None:
    with SessionLocal() as database:
        database.execute(
            delete(User).where(
                User.telegram_id.in_(TEST_TELEGRAM_IDS)
            )
        )
        database.commit()


@pytest.fixture(autouse=True)
def clean_test_users():
    remove_test_users()

    yield

    remove_test_users()


def test_happ_connect_returns_one_click_page() -> None:
    database = SessionLocal()

    try:
        user = User(
            telegram_id=996000001,
            username="happ_connect_test",
            first_name="Happ",
            is_active=True,
        )

        database.add(user)
        database.flush()

        plan = database.scalar(
            select(Plan).where(
                Plan.code == "standard_1m",
            )
        )

        assert plan is not None

        subscription = Subscription(
            user_id=user.id,
            plan_id=plan.id,
            status="active",
            starts_at=datetime.now(UTC),
            expires_at=(
                datetime.now(UTC)
                + timedelta(days=30)
            ),
        )

        database.add(subscription)
        database.commit()

        _, raw_token = (
            subscription_token_service.get_or_create_token(
                database=database,
                telegram_id=user.telegram_id,
            )
        )

        response = client.get(
            f"/connect/happ/{raw_token}"
        )

        assert response.status_code == 200

        body = response.text

        expected_subscription_url = (
            f"{settings.subscription_base_url.rstrip('/')}/"
            f"{raw_token}"
        )

        expected_happ_url = (
            f"happ://add/{expected_subscription_url}"
        )

        assert "Work&PlayVPN" in body
        assert "Открыть HAPP" in body
        assert 'id="happ-link"' in body
        assert expected_happ_url in body

        assert "window.location.replace" in body
        assert "happLink.href" in body

        assert "Открыть подписку" not in body
        assert 'class="button secondary"' not in body

        assert response.headers["cache-control"] == "no-store"
        assert response.headers["pragma"] == "no-cache"
        assert (
            response.headers["referrer-policy"]
            == "no-referrer"
        )
        assert (
            response.headers["x-robots-tag"]
            == "noindex, nofollow, noarchive"
        )

    finally:
        database.rollback()
        database.close()


def test_happ_connect_rejects_invalid_token() -> None:
    response = client.get(
        "/connect/happ/invalid-token"
    )

    assert response.status_code == 404


def test_happ_connect_requires_active_subscription() -> None:
    database = SessionLocal()

    try:
        user = User(
            telegram_id=996000002,
            username="happ_connect_no_sub",
            first_name="NoSub",
            is_active=True,
        )

        database.add(user)
        database.commit()

        _, raw_token = (
            subscription_token_service.get_or_create_token(
                database=database,
                telegram_id=user.telegram_id,
            )
        )

        response = client.get(
            f"/connect/happ/{raw_token}"
        )

        assert response.status_code == 403

    finally:
        database.rollback()
        database.close()