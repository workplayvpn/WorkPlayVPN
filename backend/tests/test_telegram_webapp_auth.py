import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

import pytest

from app.services.telegram_webapp_auth import (
    TelegramWebAppAuthError,
    validate_telegram_init_data,
)


BOT_TOKEN = "123456789:test-telegram-bot-token"
NOW = datetime(2026, 9, 9, 19, 0, tzinfo=UTC)


def build_init_data(
    *,
    auth_date: datetime = NOW,
    user_id: int = 987654321012,
    username: str = "nikita_test",
) -> str:
    fields = {
        "auth_date": str(int(auth_date.timestamp())),
        "query_id": "AAE-test-query-id",
        "user": json.dumps(
            {
                "id": user_id,
                "first_name": "Nikita",
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
        BOT_TOKEN.encode(),
        hashlib.sha256,
    ).digest()
    fields["hash"] = hmac.new(
        secret_key,
        data_check_string.encode(),
        hashlib.sha256,
    ).hexdigest()

    return urlencode(fields)


def test_accepts_valid_signed_init_data() -> None:
    result = validate_telegram_init_data(
        build_init_data(),
        bot_token=BOT_TOKEN,
        now=NOW,
    )

    assert result.user.id == 987654321012
    assert result.user.username == "nikita_test"
    assert result.user.first_name == "Nikita"
    assert result.auth_date == NOW
    assert result.query_id == "AAE-test-query-id"


def test_rejects_tampered_user_data() -> None:
    init_data = build_init_data().replace(
        "nikita_test",
        "attacker",
    )

    with pytest.raises(
        TelegramWebAppAuthError,
        match="signature",
    ):
        validate_telegram_init_data(
            init_data,
            bot_token=BOT_TOKEN,
            now=NOW,
        )


def test_rejects_expired_init_data() -> None:
    init_data = build_init_data(
        auth_date=NOW - timedelta(minutes=6),
    )

    with pytest.raises(
        TelegramWebAppAuthError,
        match="expired",
    ):
        validate_telegram_init_data(
            init_data,
            bot_token=BOT_TOKEN,
            now=NOW,
            max_age_seconds=300,
        )


def test_rejects_init_data_from_future() -> None:
    init_data = build_init_data(
        auth_date=NOW + timedelta(minutes=2),
    )

    with pytest.raises(
        TelegramWebAppAuthError,
        match="future",
    ):
        validate_telegram_init_data(
            init_data,
            bot_token=BOT_TOKEN,
            now=NOW,
        )


def test_rejects_duplicate_fields() -> None:
    init_data = (
        build_init_data()
        + "&auth_date="
        + str(int(NOW.timestamp()))
    )

    with pytest.raises(
        TelegramWebAppAuthError,
        match="duplicate",
    ):
        validate_telegram_init_data(
            init_data,
            bot_token=BOT_TOKEN,
            now=NOW,
        )
