from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def build_region_devices_keyboard(
    devices: list[dict],
) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=f"📱 {device['device_name']}",
                callback_data=f"region_device:{device['id']}",
            )
        ]
        for device in devices
    ]
    rows.append(
        [
            InlineKeyboardButton(
                text="← На главную",
                callback_data="main_menu",
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_region_locations_keyboard(
    device_id: int,
    locations: list[dict],
    *,
    current_code: str | None = None,
    back_to_devices: bool = False,
) -> InlineKeyboardMarkup:
    rows = []

    for location in locations:
        code = location["code"]
        available = location.get("available", True)
        is_current = bool(
            current_code
            and current_code.upper().startswith(code.upper())
        )

        if is_current:
            prefix = "✅"
            suffix = " · текущий"
        elif available:
            prefix = "🟢"
            suffix = ""
        else:
            prefix = "🚧"
            suffix = " · временно недоступен"

        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{prefix} {location['name']}{suffix}",
                    callback_data=f"region_location:{device_id}:{code}",
                )
            ]
        )

    rows.append(
        [
            InlineKeyboardButton(
                text=(
                    "← К выбору устройства"
                    if back_to_devices
                    else "← На главную"
                ),
                callback_data=(
                    "change_region"
                    if back_to_devices
                    else "main_menu"
                ),
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_region_result_keyboard(
    device_id: int,
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🌍 Сменить ещё раз",
                    callback_data=f"region_device:{device_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="← К подписке",
                    callback_data="subscription",
                )
            ],
        ]
    )
