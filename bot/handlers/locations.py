import httpx
from aiogram import F, Router
from aiogram.types import CallbackQuery

from api.backend import backend_get, backend_patch
from ui.devices import build_devices_keyboard
from ui.helpers import edit_screen
from ui.locations import (
    build_region_devices_keyboard,
    build_region_locations_keyboard,
    build_region_result_keyboard,
)
from ui.main import main_menu


router = Router(name="locations")


async def _get_devices(telegram_id: int) -> list[dict] | None:
    response = await backend_get(f"/devices/users/{telegram_id}")
    return response.json() if response.status_code == 200 else None


async def _get_locations() -> list[dict] | None:
    response = await backend_get("/catalog/locations")
    return response.json() if response.status_code == 200 else None


def _find_device(devices: list[dict], device_id: int) -> dict | None:
    return next(
        (device for device in devices if device["id"] == device_id),
        None,
    )


async def _show_location_picker(
    callback: CallbackQuery,
    device: dict,
) -> None:
    locations = await _get_locations()
    if locations is None:
        await edit_screen(
            callback,
            "⚠️ Не удалось загрузить регионы.",
            main_menu,
        )
        return

    await edit_screen(
        callback,
        "🌍 Смена региона\n\n"
        f"Устройство: {device['device_name']}\n"
        f"Текущий сервер: {device['node_name']}\n\n"
        "Выберите новый регион. Ключ подписки "
        "останется прежним.",
        build_region_locations_keyboard(
            device["id"],
            locations,
            current_code=device.get("node_code"),
        ),
    )


@router.callback_query(F.data.in_({"locations", "change_region"}))
async def show_region_devices(callback: CallbackQuery) -> None:
    await callback.answer()

    try:
        devices = await _get_devices(callback.from_user.id)
    except httpx.RequestError:
        devices = None

    if devices is None:
        await edit_screen(
            callback,
            "⚠️ Не удалось загрузить устройства.",
            main_menu,
        )
        return

    if not devices:
        await edit_screen(
            callback,
            "🌍 Смена региона\n\n"
            "Сначала подключите устройство.",
            build_devices_keyboard(),
        )
        return

    if len(devices) == 1:
        try:
            await _show_location_picker(callback, devices[0])
        except httpx.RequestError:
            await edit_screen(
                callback,
                "⚠️ Не удалось загрузить регионы.",
                main_menu,
            )
        return

    await edit_screen(
        callback,
        "🌍 Смена региона\n\n"
        "Выберите устройство, для которого нужно "
        "сменить регион:",
        build_region_devices_keyboard(devices),
    )


@router.callback_query(F.data.startswith("region_device:"))
async def show_device_regions(callback: CallbackQuery) -> None:
    await callback.answer()
    if callback.data is None:
        return

    device_id = int(callback.data.split(":", maxsplit=1)[1])
    try:
        devices = await _get_devices(callback.from_user.id)
        device = _find_device(devices or [], device_id)
        if device is None:
            await edit_screen(
                callback,
                "Устройство не найдено или уже отключено.",
                main_menu,
            )
            return
        await _show_location_picker(callback, device)
    except httpx.RequestError:
        await edit_screen(
            callback,
            "⚠️ Не удалось загрузить регионы.",
            main_menu,
        )


@router.callback_query(F.data.startswith("region_location:"))
async def change_device_region(callback: CallbackQuery) -> None:
    await callback.answer("Меняем регион…")
    if callback.data is None:
        return

    _, device_id_value, location_code = callback.data.split(":", maxsplit=2)
    device_id = int(device_id_value)

    try:
        response = await backend_patch(
            f"/devices/{device_id}/location",
            {
                "telegram_id": callback.from_user.id,
                "location_code": location_code,
            },
        )
    except httpx.RequestError:
        await edit_screen(
            callback,
            "⚠️ Сервис смены региона временно недоступен.",
            build_region_result_keyboard(device_id),
        )
        return

    if response.status_code == 200:
        device = response.json()
        await edit_screen(
            callback,
            "✅ Регион изменён\n\n"
            f"Устройство: {device['device_name']}\n"
            f"Новый сервер: {device['node_name']}\n\n"
            "Ключ подписки не изменился. Обновите подписку "
            "в HAPP или переподключите VPN.",
            build_region_result_keyboard(device_id),
        )
        return

    if response.status_code == 404:
        text = "Устройство или выбранный регион не найден."
    elif response.status_code in {502, 503}:
        text = "🚧 Этот регион сейчас недоступен. Выберите другой."
    else:
        text = "⚠️ Не удалось сменить регион."

    await edit_screen(
        callback,
        text,
        build_region_result_keyboard(device_id),
    )
