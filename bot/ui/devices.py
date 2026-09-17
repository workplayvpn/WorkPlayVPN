from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    WebAppInfo,
)


def build_devices_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="＋ Подключить устройство",
                    callback_data="add_device",
                )
            ],
            [
                InlineKeyboardButton(
                    text="← На главную",
                    callback_data="main_menu",
                )
            ],
        ]
    )


def build_user_devices_keyboard(
    devices: list[dict],
) -> InlineKeyboardMarkup:
    rows = []

    for device in devices:
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"📱 {device['device_name']}",
                    callback_data=f"device:{device['id']}",
                )
            ]
        )

    rows.append(
        [
                InlineKeyboardButton(
                    text="＋ Подключить устройство",
                callback_data="add_device",
            )
        ]
    )

    rows.append(
        [
                InlineKeyboardButton(
                    text="← На главную",
                callback_data="main_menu",
            )
        ]
    )

    return InlineKeyboardMarkup(
        inline_keyboard=rows,
    )


def build_device_keyboard(
    device_id: int,
    instructions_url: str | None = None,
) -> InlineKeyboardMarkup:
    if instructions_url:
        instructions_button = InlineKeyboardButton(
            text="📖 Открыть инструкцию",
            web_app=WebAppInfo(
                url=instructions_url,
            ),
        )
    else:
        instructions_button = InlineKeyboardButton(
            text="📖 Открыть инструкцию",
            callback_data=f"device_link:{device_id}",
        )

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔑 Ключ подписки",
                    callback_data=f"device_key:{device_id}",
                )
            ],
            [
                instructions_button,
            ],
            [
                InlineKeyboardButton(
                    text="⚙️ Управление",
                    callback_data=f"device_manage:{device_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="← К устройствам",
                    callback_data="devices",
                )
            ],
        ]
    )


def build_device_manage_keyboard(
    device_id: int,
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🗑 Отключить устройство",
                    callback_data=f"remove_device:{device_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="← Назад",
                    callback_data=f"device:{device_id}",
                )
            ],
        ]
    )


def build_remove_confirm_keyboard(
    device_id: int,
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Да, отключить",
                    callback_data=(
                        f"confirm_remove_device:{device_id}"
                    ),
                )
            ],
            [
                InlineKeyboardButton(
                    text="← Не отключать",
                    callback_data=f"device:{device_id}",
                )
            ],
        ]
    )


def build_locations_keyboard(
    locations: list[dict],
) -> InlineKeyboardMarkup:
    rows = []

    for location in locations:
        available = location.get("available", True)
        rows.append(
            [
                InlineKeyboardButton(
                    text=(
                        f"{'🟢' if available else '🚧'} "
                        f"{location['name']}"
                    ),
                    callback_data=(
                        f"device_location:{location['code']}"
                    ),
                )
            ]
        )

    rows.append(
        [
            InlineKeyboardButton(
                text="← К устройствам",
                callback_data="devices",
            )
        ]
    )

    return InlineKeyboardMarkup(
        inline_keyboard=rows,
    )


def build_activation_keyboard(
    activation_url: str,
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Подключить устройство →",
                    url=activation_url,
                )
            ],
            [
                InlineKeyboardButton(
                    text="Обновить список устройств",
                    callback_data="devices",
                )
            ],
            [
                InlineKeyboardButton(
                    text="← Назад",
                    callback_data="add_device",
                )
            ],
        ]
    )


def build_happ_connect_keyboard(
    *,
    connect_url: str,
    device_id: int,
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Открыть инструкцию →",
                    web_app=WebAppInfo(
                        url=connect_url,
                    ),
                )
            ],
            [
                InlineKeyboardButton(
                    text="← Назад",
                    callback_data=f"device:{device_id}",
                )
            ],
        ]
    )
