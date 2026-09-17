from __future__ import annotations

from datetime import UTC, datetime
from io import BytesIO
from math import ceil

import httpx
import qrcode
from aiogram import F, Router
from aiogram.types import BufferedInputFile, CallbackQuery

from api.backend import backend_get, backend_post
from ui.helpers import edit_screen
from ui.main import main_menu
from ui.subscription import (
    build_subscription_keyboard,
    build_subscription_secret_keyboard,
)


router = Router(name="subscription")


def _days_left(value: str | None) -> int | None:
    if not value:
        return None

    expires_at = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return max(
        0,
        ceil((expires_at - datetime.now(UTC)).total_seconds() / 86400),
    )


async def _load_subscription_data(
    telegram_id: int,
) -> tuple[dict | None, list[dict], dict | None]:
    subscription_response = await backend_get(
        f"/subscriptions/users/{telegram_id}/current"
    )

    if subscription_response.status_code == 404:
        return None, [], None

    if subscription_response.status_code != 200:
        subscription_response.raise_for_status()

    subscription = subscription_response.json()

    devices_response = await backend_get(
        f"/devices/users/{telegram_id}"
    )
    devices = (
        devices_response.json()
        if devices_response.status_code == 200
        else []
    )

    token = None
    if subscription.get("status") == "active":
        token_response = await backend_post(
            "/subscription-tokens",
            {"telegram_id": telegram_id},
        )
        if token_response.status_code == 201:
            token = token_response.json()

    return subscription, devices, token


def _build_subscription_text(
    subscription: dict | None,
    devices: list[dict],
) -> str:
    if subscription is None:
        return (
            "🔑 Моя подписка\n\n"
            "Активной подписки пока нет.\n\n"
            "Выберите тариф или запустите пробный период, "
            "чтобы подключить первое устройство."
        )

    status = subscription.get("status")
    if status != "active":
        return (
            "🔑 Моя подписка\n\n"
            "🟡 Ожидает подтверждения оплаты\n"
            f"Тариф: {subscription['plan_name']}\n\n"
            "После подтверждения платежа доступ активируется "
            "автоматически."
        )

    expires_value = subscription.get("expires_at")
    expires_at = (
        datetime.fromisoformat(expires_value.replace("Z", "+00:00"))
        if expires_value
        else None
    )
    days_left = _days_left(expires_value)
    total_limit = subscription["total_device_limit"]

    lines = [
        "🔑 Моя подписка",
        "",
        "🟢 Активна",
        f"Тариф: {subscription['plan_name']}",
        (
            f"Действует до: {expires_at:%d.%m.%Y}"
            if expires_at
            else "Действует до: уточняется"
        ),
        (
            f"Осталось: {days_left} дн."
            if days_left is not None
            else "Осталось: срок уточняется"
        ),
        f"Устройства: {len(devices)} из {total_limit}",
    ]

    if devices:
        lines.extend(["", "📱 Подключённые устройства:"])
        lines.extend(
            f"• {device['device_name']} — {device['node_name']}"
            for device in devices
        )

    lines.extend(
        [
            "",
            "Ключ и QR-код предоставляют доступ к подписке. "
            "Не пересылайте их другим людям.",
        ]
    )
    return "\n".join(lines)


@router.callback_query(F.data == "subscription")
async def show_subscription(callback: CallbackQuery) -> None:
    await callback.answer()

    try:
        subscription, devices, token = await _load_subscription_data(
            callback.from_user.id
        )
    except (httpx.HTTPError, ValueError, KeyError):
        await edit_screen(
            callback,
            "⚠️ Не удалось загрузить подписку.\n\n"
            "Попробуйте немного позже.",
            main_menu,
        )
        return

    active = bool(subscription and subscription.get("status") == "active")
    await edit_screen(
        callback,
        _build_subscription_text(subscription, devices),
        build_subscription_keyboard(
            active=active,
            connect_url=(token or {}).get("connect_url"),
        ),
    )


async def _get_token(telegram_id: int) -> dict | None:
    response = await backend_post(
        "/subscription-tokens",
        {"telegram_id": telegram_id},
    )
    return response.json() if response.status_code == 201 else None


@router.callback_query(F.data == "subscription_key")
async def show_subscription_key(callback: CallbackQuery) -> None:
    await callback.answer()

    try:
        token = await _get_token(callback.from_user.id)
    except httpx.RequestError:
        token = None

    if not token:
        await edit_screen(
            callback,
            "⚠️ Не удалось получить ключ подписки.",
            build_subscription_secret_keyboard(),
        )
        return

    await edit_screen(
        callback,
        "🔑 Ключ подписки\n\n"
        f"{token['subscription_url']}\n\n"
        "Это секретная ссылка. Не публикуйте её и не "
        "передавайте другим людям.",
        build_subscription_secret_keyboard(),
    )


@router.callback_query(F.data == "subscription_qr")
async def show_subscription_qr(callback: CallbackQuery) -> None:
    await callback.answer()

    try:
        token = await _get_token(callback.from_user.id)
    except httpx.RequestError:
        token = None

    if not token or callback.message is None:
        await edit_screen(
            callback,
            "⚠️ Не удалось подготовить QR-код.",
            build_subscription_secret_keyboard(),
        )
        return

    qr_image = qrcode.make(token["subscription_url"])
    buffer = BytesIO()
    qr_image.save(buffer, format="PNG")

    await callback.message.answer_photo(
        BufferedInputFile(
            buffer.getvalue(),
            filename="workplayvpn-subscription.png",
        ),
        caption=(
            "📷 QR-код подписки\n\n"
            "Отсканируйте его в приложении на доверенном "
            "устройстве. Не пересылайте изображение другим людям."
        ),
        reply_markup=build_subscription_secret_keyboard(),
    )
