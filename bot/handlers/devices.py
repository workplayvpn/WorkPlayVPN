from datetime import datetime

import httpx
from aiogram import F, Router
from aiogram.types import CallbackQuery

from api.backend import (
    backend_delete,
    backend_get,
    backend_post,
)
from ui.devices import (
    build_activation_keyboard,
    build_device_keyboard,
    build_device_manage_keyboard,
    build_devices_keyboard,
    build_locations_keyboard,
    build_remove_confirm_keyboard,
    build_user_devices_keyboard,
)
from ui.main import main_menu
from ui.helpers import edit_screen


router = Router(
    name="devices",
)


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


@router.callback_query(
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


@router.callback_query(
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
        "Статус: 🟢 Подключено\n"
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


@router.callback_query(
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
        "🔗 Подключение для "
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


@router.callback_query(
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


@router.callback_query(
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


@router.callback_query(
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


@router.callback_query(
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


@router.callback_query(
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