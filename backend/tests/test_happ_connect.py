from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from app.core.config import settings
from sqlalchemy import select

from app.main import app
from app.db.session import SessionLocal
from app.models.plan import Plan
from app.models.subscription import Subscription
from app.models.user import User
from app.services.subscription_token_service import (
    subscription_token_service,
)


client = TestClient(app)


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

        assert "Work&PlayVPN" in body
        assert "Подключить в HAPP" in body
        assert "happ://add/" in body
        expected_subscription_url = (
            f"{settings.subscription_base_url.rstrip('/')}/"
            f"{raw_token}"
        )

        assert (
            f"happ://add/{expected_subscription_url}"
            in body
        )
        assert raw_token in body

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