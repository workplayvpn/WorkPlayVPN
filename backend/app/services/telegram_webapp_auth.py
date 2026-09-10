import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import parse_qsl


DEFAULT_MAX_AGE_SECONDS = 300
MAX_FUTURE_SKEW_SECONDS = 30


class TelegramWebAppAuthError(ValueError):
    """Telegram Mini App authentication failed."""


@dataclass(frozen=True, slots=True)
class TelegramWebAppUser:
    id: int
    first_name: str
    last_name: str | None = None
    username: str | None = None
    language_code: str | None = None
    allows_write_to_pm: bool | None = None


@dataclass(frozen=True, slots=True)
class TelegramWebAppAuthResult:
    user: TelegramWebAppUser
    auth_date: datetime
    query_id: str | None = None


def validate_telegram_init_data(
    init_data: str,
    *,
    bot_token: str,
    now: datetime | None = None,
    max_age_seconds: int = DEFAULT_MAX_AGE_SECONDS,
) -> TelegramWebAppAuthResult:
    if not init_data:
        raise TelegramWebAppAuthError(
            "Telegram init data is missing"
        )

    if not bot_token:
        raise TelegramWebAppAuthError(
            "Telegram bot token is not configured"
        )

    if max_age_seconds <= 0:
        raise ValueError(
            "max_age_seconds must be positive"
        )

    try:
        pairs = parse_qsl(
            init_data,
            keep_blank_values=True,
            strict_parsing=True,
        )
    except ValueError as exc:
        raise TelegramWebAppAuthError(
            "Telegram init data is malformed"
        ) from exc

    fields: dict[str, str] = {}

    for key, value in pairs:
        if key in fields:
            raise TelegramWebAppAuthError(
                f"Telegram init data contains duplicate field: {key}"
            )

        fields[key] = value

    received_hash = fields.pop("hash", None)

    if received_hash is None:
        raise TelegramWebAppAuthError(
            "Telegram init data signature is missing"
        )

    data_check_string = "\n".join(
        f"{key}={value}"
        for key, value in sorted(fields.items())
    )

    secret_key = hmac.new(
        b"WebAppData",
        bot_token.encode(),
        hashlib.sha256,
    ).digest()
    expected_hash = hmac.new(
        secret_key,
        data_check_string.encode(),
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(
        received_hash,
        expected_hash,
    ):
        raise TelegramWebAppAuthError(
            "Telegram init data signature is invalid"
        )

    auth_date_raw = fields.get("auth_date")

    try:
        auth_timestamp = int(auth_date_raw or "")
        auth_date = datetime.fromtimestamp(
            auth_timestamp,
            tz=UTC,
        )
    except (ValueError, OverflowError) as exc:
        raise TelegramWebAppAuthError(
            "Telegram auth_date is invalid"
        ) from exc

    current_time = now or datetime.now(UTC)

    if current_time.tzinfo is None:
        raise ValueError(
            "now must be timezone-aware"
        )

    current_time = current_time.astimezone(UTC)
    age_seconds = (
        current_time - auth_date
    ).total_seconds()

    if age_seconds < -MAX_FUTURE_SKEW_SECONDS:
        raise TelegramWebAppAuthError(
            "Telegram init data is from the future"
        )

    if age_seconds > max_age_seconds:
        raise TelegramWebAppAuthError(
            "Telegram init data has expired"
        )

    user_raw = fields.get("user")

    if user_raw is None:
        raise TelegramWebAppAuthError(
            "Telegram user data is missing"
        )

    try:
        user_payload = json.loads(user_raw)
    except json.JSONDecodeError as exc:
        raise TelegramWebAppAuthError(
            "Telegram user data is malformed"
        ) from exc

    if not isinstance(user_payload, dict):
        raise TelegramWebAppAuthError(
            "Telegram user data is invalid"
        )

    user_id = user_payload.get("id")
    first_name = user_payload.get("first_name")

    if (
        isinstance(user_id, bool)
        or not isinstance(user_id, int)
        or user_id <= 0
    ):
        raise TelegramWebAppAuthError(
            "Telegram user id is invalid"
        )

    if not isinstance(first_name, str) or not first_name:
        raise TelegramWebAppAuthError(
            "Telegram user first name is invalid"
        )

    optional_string_fields = (
        "last_name",
        "username",
        "language_code",
    )

    for field_name in optional_string_fields:
        value = user_payload.get(field_name)

        if value is not None and not isinstance(value, str):
            raise TelegramWebAppAuthError(
                f"Telegram user {field_name} is invalid"
            )

    allows_write_to_pm = user_payload.get(
        "allows_write_to_pm"
    )

    if (
        allows_write_to_pm is not None
        and not isinstance(allows_write_to_pm, bool)
    ):
        raise TelegramWebAppAuthError(
            "Telegram user allows_write_to_pm is invalid"
        )

    query_id = fields.get("query_id")

    return TelegramWebAppAuthResult(
        user=TelegramWebAppUser(
            id=user_id,
            first_name=first_name,
            last_name=user_payload.get("last_name"),
            username=user_payload.get("username"),
            language_code=user_payload.get("language_code"),
            allows_write_to_pm=allows_write_to_pm,
        ),
        auth_date=auth_date,
        query_id=query_id,
    )
