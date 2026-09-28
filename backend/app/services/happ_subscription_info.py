"""Presentation metadata for Happ subscriptions."""

import base64
from datetime import UTC, datetime


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
