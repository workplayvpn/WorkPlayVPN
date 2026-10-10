"""Presentation metadata for Happ subscriptions."""

from app.services.rollout_access import rollout_allowed

import base64
import re
from urllib.parse import urlsplit, urlunsplit
from datetime import UTC, datetime


def hidden_settings_metadata(*, provider_id: str, user_id: int, allowed_ids: str) -> dict[str, str]:
    """Provider controls require a valid provider and explicit rollout setting."""
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", provider_id):
        return {}
    if not rollout_allowed(allowed_ids, user_id):
        return {}
    return {"providerid": provider_id, "hide-settings": "1"}


def happ_server_description(link: str, description: str) -> str:
    """Replace Happ's protocol subtitle without changing the VLESS endpoint."""
    parts = urlsplit(link)
    if parts.scheme != "vless" or not parts.fragment:
        return link
    name = parts.fragment.split("?serverDescription=", 1)[0]
    encoded = base64.b64encode(description.encode("utf-8")).decode("ascii")
    return urlunsplit((parts.scheme, parts.netloc, parts.path, parts.query,
                       f"{name}?serverDescription={encoded}"))


BASIC_DESCRIPTION = "Надёжное подключение через Wi-Fi. Выбор региона через Telegram бота. Бот: @workplayvpn_bot"
PRO_DESCRIPTION = "Подключение для Wi-Fi и мобильной сети. Маршрут выбирается автоматически. Выбор региона через Telegram бота. Бот: @workplayvpn_bot"


def subscription_presentation(*, access_tier: str, routed_mobile: bool = False) -> dict[str, str]:
    if access_tier == "basic":
        title = "Work&PlayVPN Basic"
        description = BASIC_DESCRIPTION
    elif access_tier == "mobile":
        title = "Work&PlayVPN Pro"
        description = PRO_DESCRIPTION
    else:
        raise ValueError("Unknown subscription tier")
    encoded = base64.b64encode(description.encode("utf-8")).decode("ascii")
    return {
        "profile-title": title, "announce": f"base64:{encoded}",
        "profile-web-page-url": f"https://t.me/workplayvpn_bot?startapp=subscription_{access_tier}",
    }


def subscription_expiry_info(expires_at: datetime | None) -> str | None:
    """Report only the known expiry; traffic counters are not available here."""
    if expires_at is None:
        return None
    if expires_at.tzinfo is None:
        raise ValueError("Subscription expiry must include a timezone")
    return f"expire={int(expires_at.astimezone(UTC).timestamp())}"
