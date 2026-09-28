"""Presentation metadata for Happ subscriptions."""

import base64
import re
from urllib.parse import urlsplit, urlunsplit
from datetime import UTC, datetime


def hidden_settings_metadata(*, provider_id: str, user_id: int, allowed_ids: str) -> dict[str, str]:
    """Keep Happ's provider controls limited to explicitly selected users."""
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", provider_id):
        return {}
    if str(user_id) not in {part.strip() for part in allowed_ids.split(",") if part.strip().isdigit()}:
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


def subscription_presentation(*, access_tier: str, routed_mobile: bool = False) -> dict[str, str]:
    if access_tier == "basic":
        title = "Work&PlayVPN Basic"
        description = "Надёжное подключение для работы и отдыха."
    elif access_tier == "mobile":
        title = "Work&PlayVPN Mobile"
        description = (
            "Подключение для Wi-Fi и мобильной сети. "
            "Маршрут выбирается автоматически."
            if routed_mobile else
            "Для подключения выберите профиль Wi-Fi или Mobile в Happ."
        )
    else:
        raise ValueError("Unknown subscription tier")
    encoded = base64.b64encode(description.encode("utf-8")).decode("ascii")
    return {"profile-title": title, "announce": f"base64:{encoded}"}


def subscription_expiry_info(expires_at: datetime | None) -> str | None:
    """Report only the known expiry; traffic counters are not available here."""
    if expires_at is None:
        return None
    if expires_at.tzinfo is None:
        raise ValueError("Subscription expiry must include a timezone")
    return f"expire={int(expires_at.astimezone(UTC).timestamp())}"
