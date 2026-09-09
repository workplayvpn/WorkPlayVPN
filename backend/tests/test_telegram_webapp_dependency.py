import hashlib
import hmac
import json
from datetime import UTC, datetime
from urllib.parse import urlencode

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.api.telegram_webapp_auth import (
    require_telegram_webapp_auth,
)
from app.core.config import settings
from app.services.telegram_webapp_auth import (
    TelegramWebAppAuthResult,
)


BOT_TOKEN = "123456789:test-telegram-bot-token"


def build_current_init_data() -> str:
    fields = {
        "auth_date": str(
            int(datetime.now(UTC).timestamp())
        ),
        "query_id": "AAE-dependency-test",
        "user": json.dumps(
            {
                "id": 987654321012,
                "first_name": "Nikita",
                "username": "nikita_test",
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


dependency_app = FastAPI()


@dependency_app.get("/protected")
def protected_route(
    auth: TelegramWebAppAuthResult = Depends(
        require_telegram_webapp_auth
    ),
):
    return {
        "telegram_id": auth.user.id,
    }


client = TestClient(dependency_app)


def test_missing_init_data_is_rejected(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        settings,
        "telegram_bot_token",
        BOT_TOKEN,
    )

    response = client.get("/protected")

    assert response.status_code == 401
    assert response.json() == {
        "detail": "Invalid Telegram Mini App credentials"
    }


def test_invalid_init_data_is_rejected(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        settings,
        "telegram_bot_token",
        BOT_TOKEN,
    )

    response = client.get(
        "/protected",
        headers={
            "X-Telegram-Init-Data": "forged=true",
        },
    )

    assert response.status_code == 401


def test_valid_init_data_is_accepted(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        settings,
        "telegram_bot_token",
        BOT_TOKEN,
    )

    response = client.get(
        "/protected",
        headers={
            "X-Telegram-Init-Data": build_current_init_data(),
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "telegram_id": 987654321012,
    }


def test_missing_bot_token_is_server_error(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        settings,
        "telegram_bot_token",
        None,
    )

    response = client.get(
        "/protected",
        headers={
            "X-Telegram-Init-Data": build_current_init_data(),
        },
    )

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Telegram Mini App authentication is unavailable"
    }
