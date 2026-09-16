from datetime import datetime

import httpx
from aiogram import F, Router
from aiogram.types import CallbackQuery

from api.backend import backend_get
from ui.common import build_back_to_main_keyboard
from ui.main import main_menu
from ui.helpers import edit_screen


router = Router(
    name="profile",
)


@router.callback_query(
    F.data == "profile"
)
async def show_profile(
    callback: CallbackQuery,
) -> None:
    await callback.answer()

    try:
        user_response = await backend_get(
            f"/users/{callback.from_user.id}"
        )

        subscription_response = await backend_get(
            "/subscriptions/users/"
            f"{callback.from_user.id}/current"
        )
    except httpx.RequestError:
        await edit_screen(
            callback,
            "⚠️ Не удалось загрузить профиль.",
            main_menu,
        )
        return

    if user_response.status_code != 200:
        await edit_screen(
            callback,
            "Профиль не найден.\n"
            "Отправьте /start.",
            main_menu,
        )
        return

    user = user_response.json()

    username = (
        f"@{user['username']}"
        if user["username"]
        else "не указан"
    )

    lines = [
        "👤 Профиль Work&PlayVPN",
        "",
        f"Аккаунт: {username}",
        f"Telegram ID: {user['telegram_id']}",
    ]

    if subscription_response.status_code == 200:
        subscription = (
            subscription_response.json()
        )

        status_names = {
            "active": "🟢 Активна",
            "pending": "🟡 Ожидает оплаты",
            "expired": "🔴 Закончилась",
            "cancelled": "⚪ Отменена",
        }

        lines.extend(
            [
                "",
                "🛡 Подписка",
                f"Тариф: {subscription['plan_name']}",
                "Статус: "
                f"{status_names.get(subscription['status'], subscription['status'])}",
                "Устройства: до "
                f"{subscription['total_device_limit']}",
            ]
        )

        if subscription["expires_at"]:
            expires_at = datetime.fromisoformat(
                subscription["expires_at"].replace(
                    "Z",
                    "+00:00",
                )
            )

            lines.append(
                "Действует до: "
                f"{expires_at:%d.%m.%Y}"
            )

    else:
        lines.extend(
            [
                "",
                "🛡 Подписка",
                "Нет активной подписки.",
                "Выберите тариф, чтобы подключиться.",
            ]
        )

    await edit_screen(
        callback,
        "\n".join(lines),
        build_back_to_main_keyboard(),
    )
