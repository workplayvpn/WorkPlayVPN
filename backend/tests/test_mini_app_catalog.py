import hashlib
import hmac
import json
from datetime import UTC, datetime
from decimal import Decimal
from urllib.parse import urlencode

from fastapi.testclient import TestClient
from sqlalchemy import delete, select
import pytest

from app.core.config import settings
from app.db.session import SessionLocal
from app.main import app
from app.models.plan import Plan
from app.models.user import User


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


def test_mobile_durations_are_available_with_pilot_prices() -> None:
    with SessionLocal() as database:
        plans = database.scalars(
            select(Plan)
            .where(Plan.access_tier == "mobile")
            .order_by(Plan.duration_days)
        ).all()

        assert [
            (plan.code, plan.duration_days, str(plan.price_amount))
            for plan in plans
        ] == [
            ("mobile_7d", 7, "99.00"),
            ("mobile_1m", 30, "249.00"),
            ("mobile_3m", 90, "699.00"),
            ("mobile_6m", 180, "1299.00"),
            ("mobile_12m", 365, "2290.00"),
        ]
        assert all(plan.is_active for plan in plans if plan.code != "mobile_1m")


def test_catalog_exposes_mobile_only_to_pilot_users(monkeypatch: pytest.MonkeyPatch) -> None:
    code = "mobile_catalog_test"
    monkeypatch.setattr(settings, "mobile_pilot_user_ids", "")
    with SessionLocal() as db:
        user = User(telegram_id=993100002, first_name="Catalog", is_active=True)
        db.add(user)
        db.add(Plan(
            code=code, name="Mobile test", duration_days=30,
            price_amount=Decimal("299.00"), currency="RUB",
            access_tier="mobile", device_limit=1, is_active=True,
        ))
        db.commit()
        pilot_user_id = user.id

    try:
        headers = {"X-Telegram-Init-Data": build_init_data()}
        response = client.get(
            "/mini-app/catalog",
            headers=headers,
        )
        assert response.status_code == 200
        assert all(plan["access_tier"] == "basic" for plan in response.json()["plans"])

        monkeypatch.setattr(settings, "mobile_pilot_user_ids", str(pilot_user_id))
        response = client.get("/mini-app/catalog", headers=headers)
        assert response.status_code == 200
        mobile_plans = [
            plan for plan in response.json()["plans"]
            if plan["access_tier"] == "mobile"
        ]
        assert {(plan["code"], plan["price_amount"]) for plan in mobile_plans} >= {
            (code, "299.00"),
            ("mobile_7d", "99.00"),
            ("mobile_3m", "699.00"),
            ("mobile_6m", "1299.00"),
            ("mobile_12m", "2290.00"),
        }
    finally:
        with SessionLocal() as db:
            db.execute(delete(Plan).where(Plan.code == code))
            db.execute(delete(User).where(User.telegram_id == 993100002))
            db.commit()


def test_bot_catalog_matches_mini_app_and_protects_mobile(monkeypatch):
    headers = {"Authorization": f"Bearer {settings.internal_api_secret}"}
    assert client.get("/catalog/users/993100002/plans").status_code == 401
    with SessionLocal() as db:
        existing = db.scalar(select(User).where(User.telegram_id == 993100002))
        user = existing or User(telegram_id=993100002, first_name="Catalog", is_active=True)
        db.add(user)
        db.commit()
        pilot_id = user.id
    try:
        for pilot in ("", str(pilot_id), "*"):
            monkeypatch.setattr(settings, "mobile_pilot_user_ids", pilot)
            bot = client.get("/catalog/users/993100002/plans", headers=headers)
            mini = client.get("/mini-app/catalog", headers={"X-Telegram-Init-Data": build_init_data()})
            assert bot.status_code == mini.status_code == 200
            bot_paid = {p["code"] for p in bot.json() if p["code"] != "trial_1d"}
            assert bot_paid == {p["code"] for p in mini.json()["plans"]}
            assert any(p["access_tier"] == "mobile" for p in bot.json()) == bool(pilot)
    finally:
        if existing is None:
            with SessionLocal() as db:
                db.execute(delete(User).where(User.telegram_id == 993100002))
                db.commit()
