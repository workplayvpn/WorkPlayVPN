from typing import Annotated

from fastapi import Header, HTTPException, status

from app.core.config import settings
from app.services.telegram_webapp_auth import (
    TelegramWebAppAuthError,
    TelegramWebAppAuthResult,
    validate_telegram_init_data,
)


def require_telegram_webapp_auth(
    init_data: Annotated[
        str | None,
        Header(alias="X-Telegram-Init-Data"),
    ] = None,
) -> TelegramWebAppAuthResult:
    bot_token = settings.telegram_bot_token

    if not bot_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Telegram Mini App authentication "
                "is unavailable"
            ),
        )

    try:
        return validate_telegram_init_data(
            init_data or "",
            bot_token=bot_token,
        )
    except TelegramWebAppAuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Telegram Mini App credentials",
            headers={
                "WWW-Authenticate": "Telegram-Init-Data",
            },
        ) from exc
