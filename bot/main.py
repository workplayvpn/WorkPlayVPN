import asyncio
import os
from datetime import datetime

import httpx
from aiogram import Bot, Dispatcher, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, Message

from keyboards import (
    build_back_to_main_keyboard,
    build_device_keyboard,
    build_device_manage_keyboard,
    build_devices_keyboard,
    build_locations_keyboard,
    build_plans_keyboard,
    build_remove_confirm_keyboard,
    build_user_devices_keyboard,
    build_activation_keyboard,
    main_menu,
)


telegram_bot_token = os.environ["TELEGRAM_BOT_TOKEN"]

backend_url = os.getenv(
    "BACKEND_URL",
    "http://backend:8000",
)

dispatcher = Dispatcher()


async def backend_get(
    path: str,
) -> httpx.Response:
    async with httpx.AsyncClient(
        timeout=10.0
    ) as client:
        return await client.get(
            f"{backend_url}{path}"
        )


async def backend_post(
    path: str,
    payload: dict,
) -> httpx.Response:
    async with httpx.AsyncClient(
        timeout=10.0
    ) as client:
        return await client.post(
            f"{backend_url}{path}",
            json=payload,
        )


async def backend_delete(
    path: str,
) -> httpx.Response:
    async with httpx.AsyncClient(
        timeout=10.0
    ) as client:
        return await client.delete(
            f"{backend_url}{path}"
        )


async def edit_screen(
    callback: CallbackQuery,
    text: str,
    reply_markup=None,
) -> None:
    if callback.message is None:
        return

    try:
        await callback.message.edit_text(
            text,
            reply_markup=reply_markup,
        )
    except TelegramBadRequest as exc:
        if "message is not modified" in str(exc):
            return

        raise


async def get_user_devices(
    telegram_id: int,
) -> list[dict] | None:
    response = await backend_get(
        f"/devices/users/{telegram_id}"
    )

    if response.status_code != 200:
        return None

    return response.json()


async def find_device(
    telegram_id: int,
    device_id: int,
) -> dict | None:
    devices = await get_user_devices(
        telegram_id
    )

    if devices is None:
        return None

    for device in devices:
        if device["id"] == device_id:
            return device

    return None


@dispatcher.message(CommandStart())
async def handle_start(
    message: Message,
) -> None:
    telegram_user = message.from_user

    if telegram_user is None:
        return

    payload = {
        "telegram_id": telegram_user.id,
        "username": telegram_user.username,
        "first_name": telegram_user.first_name,
    }

    try:
        response = await backend_post(
            "/users",
            payload,
        )
    except httpx.RequestError:
        await message.answer(
            "⚠️ Сервис временно недоступен.\n"
            "Попробуйте немного позже."
        )
        return

    if response.status_code == 201:
        greeting = (
            f"Добро пожаловать, "
            f"{telegram_user.first_name}!"
        )
    elif response.status_code == 409:
        greeting = (
            f"С возвращением, "
            f"{telegram_user.first_name}!"
        )
    else:
        await message.answer(
            "Не удалось загрузить профиль."
        )
        return

    text = (
        "🛡 Work&PlayVPN\n\n"
        f"{greeting}\n\n"
        "Быстрый и безопасный доступ "
        "к интернету.\n\n"
        "Выберите нужный раздел:"
    )

    await message.answer(
        text,
        reply_markup=main_menu,
    )


@dispatcher.callback_query(
    F.data == "main_menu"
)
async def show_main_menu(
    callback: CallbackQuery,
) -> None:
    await callback.answer()

    await edit_screen(
        callback,
        "🛡 Work&PlayVPN\n\n"
        "Главное меню\n\n"
        "Выберите нужный раздел:",
        main_menu,
    )


@dispatcher.callback_query(
    F.data == "plans"
)
async def show_plans(
    callback: CallbackQuery,
) -> None:
    await callback.answer()

    try:
        response = await backend_get(
            "/catalog/plans"
        )
    except httpx.RequestError:
        await edit_screen(
            callback,
            "⚠️ Не удалось загрузить тарифы.",
            main_menu,
        )
        return

    if response.status_code != 200:
        await edit_screen(
            callback,
            "⚠️ Не удалось загрузить тарифы.",
            main_menu,
        )
        return

    plans = response.json()

    lines = [
        "💳 Тарифы Work&PlayVPN",
        "",
    ]

    for plan in plans:
        price = str(
            plan["price_amount"]
        ).removesuffix(".00")

        devices = plan["device_limit"]

        if plan["code"] == "trial_1d":
            lines.append(
                f"🎁 {plan['name']}\n"
                f"   3 дня • "
                f"{devices} устройство • бесплатно"
            )
        else:
            lines.append(
                f"• {plan['name']}\n"
                f"   {price} ₽ • "
                f"до {devices} устройств"
            )

    lines.extend(
        [
            "",
            "➕ Дополнительное устройство: 249 ₽",
            "",
            "Выберите тариф:",
        ]
    )

    await edit_screen(
        callback,
        "\n".join(lines),
        build_plans_keyboard(plans),
    )


@dispatcher.callback_query(
    F.data.startswith("select_plan:")
)
async def select_plan(
    callback: CallbackQuery,
) -> None:
    await callback.answer()

    if callback.data is None:
        return

    plan_code = callback.data.split(
        ":",
        maxsplit=1,
    )[1]

    payload = {
        "telegram_id": callback.from_user.id,
        "plan_code": plan_code,
    }

    try:
        response = await backend_post(
            "/subscriptions",
            payload,
        )
    except httpx.RequestError:
        await edit_screen(
            callback,
            "⚠️ Не удалось оформить тариф.",
            main_menu,
        )
        return

    if response.status_code == 201:
        subscription = response.json()

        if subscription["status"] == "active":
            text = (
                "🎉 Пробный период активирован!\n\n"
                "Срок: 3 дня\n"
                "Устройств: 1\n\n"
                "Теперь можно подключить устройство."
            )
        else:
            text = (
                "✅ Тариф выбран.\n\n"
                "Статус: ожидает оплаты.\n\n"
                "Платёжная система будет "
                "подключена позже."
            )

        await edit_screen(
            callback,
            text,
            main_menu,
        )
        return

    if response.status_code == 409:
        detail = response.json().get(
            "detail"
        )

        messages = {
            "Trial already used": (
                "🎁 Пробный период уже был использован."
            ),
            "Payment already pending": (
                "💳 Оплата этого тарифа уже ожидается."
            ),
            "User already has active subscription": (
                "✅ У вас уже есть активная подписка."
            ),
        }

        await edit_screen(
            callback,
            messages.get(
                detail,
                "Этот тариф сейчас недоступен.",
            ),
            main_menu,
        )
        return

    await edit_screen(
        callback,
        "⚠️ Не удалось оформить тариф.",
        main_menu,
    )


@dispatcher.callback_query(
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
        "👤 Мой профиль",
        "",
        f"Telegram ID: {user['telegram_id']}",
        f"Username: {username}",
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
                "💳 Подписка",
                f"Тариф: {subscription['plan_name']}",
                "Статус: "
                f"{status_names.get(subscription['status'], subscription['status'])}",
                "Лимит устройств: "
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
                "💳 Подписка",
                "Подписка не оформлена.",
            ]
        )

    await edit_screen(
        callback,
        "\n".join(lines),
        build_back_to_main_keyboard(),
    )


@dispatcher.callback_query(
    F.data == "locations"
)
async def show_locations(
    callback: CallbackQuery,
) -> None:
    await callback.answer()

    try:
        response = await backend_get(
            "/catalog/locations"
        )
    except httpx.RequestError:
        await edit_screen(
            callback,
            "⚠️ Не удалось загрузить локации.",
            main_menu,
        )
        return

    if response.status_code != 200:
        await edit_screen(
            callback,
            "⚠️ Не удалось загрузить локации.",
            main_menu,
        )
        return

    lines = [
        "🌍 Локации Work&PlayVPN",
        "",
    ]

    for location in response.json():
        lines.append(
            f"• {location['name']}"
        )

    lines.extend(
        [
            "",
            "Доступность серверов "
            "будет расширяться постепенно.",
        ]
    )

    await edit_screen(
        callback,
        "\n".join(lines),
        build_back_to_main_keyboard(),
    )


@dispatcher.callback_query(
    F.data == "devices"
)
async def show_devices(
    callback: CallbackQuery,
) -> None:
    await callback.answer()

    try:
        response = await backend_get(
            f"/devices/users/{callback.from_user.id}"
        )
    except httpx.RequestError:
        await edit_screen(
            callback,
            "⚠️ Не удалось загрузить устройства.",
            main_menu,
        )
        return

    if response.status_code == 404:
        await edit_screen(
            callback,
            "Профиль не найден.\n"
            "Отправьте /start.",
            main_menu,
        )
        return

    if response.status_code != 200:
        await edit_screen(
            callback,
            "⚠️ Не удалось загрузить устройства.",
            main_menu,
        )
        return

    devices = response.json()

    if not devices:
        await edit_screen(
            callback,
            "📱 Мои устройства\n\n"
            "У вас пока нет подключённых устройств.\n\n"
            "Нажмите кнопку ниже, "
            "чтобы подключить первое устройство.",
            build_devices_keyboard(),
        )
        return

    lines = [
        "📱 Мои устройства",
        "",
        f"Подключено: {len(devices)}",
        "",
    ]

    for device in devices:
        lines.append(
            f"🟢 {device['device_name']}\n"
            f"   {device['node_name']}"
        )

    lines.extend(
        [
            "",
            "Выберите устройство "
            "для управления:",
        ]
    )

    await edit_screen(
        callback,
        "\n".join(lines),
        build_user_devices_keyboard(
            devices
        ),
    )


@dispatcher.callback_query(
    F.data.startswith("device:")
)
async def show_device(
    callback: CallbackQuery,
) -> None:
    await callback.answer()

    if callback.data is None:
        return

    device_id = int(
        callback.data.split(
            ":",
            maxsplit=1,
        )[1]
    )

    try:
        device = await find_device(
            callback.from_user.id,
            device_id,
        )
    except httpx.RequestError:
        await edit_screen(
            callback,
            "⚠️ Не удалось загрузить устройство.",
            build_devices_keyboard(),
        )
        return

    if device is None:
        await edit_screen(
            callback,
            "Устройство не найдено "
            "или уже отключено.",
            build_devices_keyboard(),
        )
        return

    text = (
        f"📱 {device['device_name']}\n\n"
        f"Статус: 🟢 Подключено\n"
        f"Локация: {device['node_name']}\n"
        f"Код сервера: {device['node_code']}\n\n"
        "Выберите действие:"
    )

    await edit_screen(
        callback,
        text,
        build_device_keyboard(
            device_id
        ),
    )


@dispatcher.callback_query(
    F.data.startswith("device_link:")
)
async def show_device_link(
    callback: CallbackQuery,
) -> None:
    await callback.answer()

    if callback.data is None:
        return

    device_id = int(
        callback.data.split(
            ":",
            maxsplit=1,
        )[1]
    )

    try:
        device = await find_device(
            callback.from_user.id,
            device_id,
        )
    except httpx.RequestError:
        await edit_screen(
            callback,
            "⚠️ Не удалось получить подключение.",
            build_devices_keyboard(),
        )
        return

    if device is None:
        await edit_screen(
            callback,
            "Устройство не найдено "
            "или уже отключено.",
            build_devices_keyboard(),
        )
        return

    text = (
        f"🔗 Подключение для "
        f"{device['device_name']}\n\n"
        "Скопируйте ссылку и импортируйте "
        "её в совместимое приложение.\n\n"
        f"{device['vless_url']}\n\n"
        "После импорта сохраните профиль "
        "в приложении."
    )

    await edit_screen(
        callback,
        text,
        build_device_keyboard(
            device_id
        ),
    )


@dispatcher.callback_query(
    F.data.startswith("device_manage:")
)
async def manage_device(
    callback: CallbackQuery,
) -> None:
    await callback.answer()

    if callback.data is None:
        return

    device_id = int(
        callback.data.split(
            ":",
            maxsplit=1,
        )[1]
    )

    await edit_screen(
        callback,
        "⚙️ Управление устройством\n\n"
        "Отвязка используется, если устройство "
        "потеряно, продано или вы хотите "
        "освободить слот подписки.",
        build_device_manage_keyboard(
            device_id
        ),
    )


@dispatcher.callback_query(
    F.data.startswith("remove_device:")
)
async def request_remove_device(
    callback: CallbackQuery,
) -> None:
    await callback.answer()

    if callback.data is None:
        return

    device_id = int(
        callback.data.split(
            ":",
            maxsplit=1,
        )[1]
    )

    await edit_screen(
        callback,
        "⚠️ Отвязать устройство?\n\n"
        "Текущая VPN-конфигурация "
        "перестанет работать.\n\n"
        "Подписка при этом останется активной.",
        build_remove_confirm_keyboard(
            device_id
        ),
    )


@dispatcher.callback_query(
    F.data.startswith(
        "confirm_remove_device:"
    )
)
async def confirm_remove_device(
    callback: CallbackQuery,
) -> None:
    await callback.answer()

    if callback.data is None:
        return

    device_id = callback.data.split(
        ":",
        maxsplit=1,
    )[1]

    try:
        response = await backend_delete(
            f"/devices/{device_id}"
            f"?telegram_id={callback.from_user.id}"
        )
    except httpx.RequestError:
        await edit_screen(
            callback,
            "⚠️ VPN-сервер временно недоступен.",
            build_devices_keyboard(),
        )
        return

    if response.status_code == 200:
        device = response.json()

        await edit_screen(
            callback,
            "✅ Устройство отвязано\n\n"
            f"📱 {device['device_name']}\n\n"
            "VPN-доступ для этого устройства "
            "отозван.",
            build_devices_keyboard(),
        )
        return

    if response.status_code == 404:
        await edit_screen(
            callback,
            "Устройство уже отключено "
            "или не найдено.",
            build_devices_keyboard(),
        )
        return

    await edit_screen(
        callback,
        "⚠️ Не удалось отвязать устройство.",
        build_devices_keyboard(),
    )


@dispatcher.callback_query(
    F.data == "add_device"
)
async def add_device(
    callback: CallbackQuery,
) -> None:
    await callback.answer()

    try:
        response = await backend_get(
            "/catalog/locations"
        )
    except httpx.RequestError:
        await edit_screen(
            callback,
            "⚠️ Не удалось загрузить страны.",
            build_devices_keyboard(),
        )
        return

    if response.status_code != 200:
        await edit_screen(
            callback,
            "⚠️ Не удалось загрузить страны.",
            build_devices_keyboard(),
        )
        return

    locations = response.json()

    await edit_screen(
        callback,
        "🌍 Выберите локацию\n\n"
        "Выберите страну, "
        "через которую будет работать VPN:",
        build_locations_keyboard(
            locations
        ),
    )


@dispatcher.callback_query(
    F.data.startswith("device_location:")
)
async def select_device_location(
    callback: CallbackQuery,
) -> None:
    await callback.answer()

    if callback.data is None:
        return

    location_code = callback.data.split(
        ":",
        maxsplit=1,
    )[1]

    # Пока физически работает только NL-01.
    # Позже эту проверку перенесём полностью в backend.
    if location_code != "NL":
        await edit_screen(
            callback,
            "🚧 Эта локация пока готовится.\n\n"
            "Сейчас для подключения "
            "доступны Нидерланды.",
            build_devices_keyboard(),
        )
        return

    payload = {
        "telegram_id": callback.from_user.id,
        "location_code": location_code,
    }

    try:
        response = await backend_post(
            "/device-activations",
            payload,
        )
    except httpx.RequestError:
        await edit_screen(
            callback,
            "⚠️ Не удалось создать ссылку подключения.",
            build_devices_keyboard(),
        )
        return

    if response.status_code == 201:
        activation = response.json()

        expires_at = datetime.fromisoformat(
            activation["expires_at"].replace(
                "Z",
                "+00:00",
            )
        )

        text = (
            "📱 Подключение устройства\n\n"
            "Откройте ссылку на том устройстве, "
            "которое хотите подключить.\n\n"
            "Work&PlayVPN автоматически определит "
            "тип устройства и создаст "
            "персональную VPN-конфигурацию.\n\n"
            "⏳ Ссылка одноразовая и действует "
            "15 минут.\n\n"
            "Истекает: "
            f"{expires_at:%H:%M} UTC"
        )

        await edit_screen(
            callback,
            text,
            build_activation_keyboard(
                activation["activation_url"]
            ),
        )
        return

    if response.status_code == 403:
        detail = response.json().get(
            "detail"
        )

        messages = {
            "Active subscription required": (
                "🔒 Для подключения устройства "
                "нужна активная подписка."
            ),
            "Subscription expired": (
                "⌛ Срок вашей подписки закончился."
            ),
        }

        await edit_screen(
            callback,
            messages.get(
                detail,
                "Подключение сейчас недоступно.",
            ),
            main_menu,
        )
        return

    if response.status_code == 409:
        detail = response.json().get(
            "detail"
        )

        if detail == "Device limit reached":
            text = (
                "📱 Достигнут лимит устройств.\n\n"
                "Отвяжите старое устройство "
                "или приобретите дополнительный слот."
            )
        else:
            text = (
                "⚠️ Не удалось создать "
                "ссылку подключения."
            )

        await edit_screen(
            callback,
            text,
            build_devices_keyboard(),
        )
        return

    if response.status_code == 404:
        await edit_screen(
            callback,
            "🌍 Выбранная локация недоступна.",
            build_devices_keyboard(),
        )
        return

    await edit_screen(
        callback,
        "⚠️ Не удалось создать ссылку подключения.",
        build_devices_keyboard(),
    )


@dispatcher.callback_query(
    F.data == "help"
)
async def show_help(
    callback: CallbackQuery,
) -> None:
    await callback.answer()

    text = (
        "❓ Помощь\n\n"
        "1. Выберите тариф.\n"
        "2. Активируйте подписку.\n"
        "3. Откройте «Мои устройства».\n"
        "4. Подключите устройство.\n"
        "5. Импортируйте полученную "
        "VLESS-ссылку в VPN-клиент.\n\n"
        "Поддержка и подробные инструкции "
        "будут добавлены позже."
    )

    await edit_screen(
        callback,
        text,
        build_back_to_main_keyboard(),
    )


async def main() -> None:
    bot = Bot(
        token=telegram_bot_token
    )

    try:
        await bot.delete_webhook(
            drop_pending_updates=True
        )

        await dispatcher.start_polling(
            bot
        )

    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())