from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    WebAppInfo,
)

from config import mini_app_devices_url
from ui.common import build_keyboard


def build_devices_keyboard() -> InlineKeyboardMarkup:
    return build_keyboard(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Открыть устройства в приложении",
                    web_app=WebAppInfo(
                        url=mini_app_devices_url,
                    ),
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

    rows.append([InlineKeyboardButton(text="➕ Добавить лимит устройств", callback_data="device_slots", style="primary")])

    rows.append(
        [
            InlineKeyboardButton(
                text="Открыть устройства в приложении",
                web_app=WebAppInfo(
                    url=mini_app_devices_url,
                ),
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

    return build_keyboard(
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

    return build_keyboard(
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
    return build_keyboard(
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
    return build_keyboard(
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


def build_activation_keyboard(
    activation_url: str,
) -> InlineKeyboardMarkup:
    return build_keyboard(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Подключить устройство →",
                    style="primary",
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
                    text="← К устройствам",
                    callback_data="devices",
                )
            ],
        ]
    )


def build_happ_connect_keyboard(
    *,
    connect_url: str,
    device_id: int,
    mobile_connect_url: str | None = None,
) -> InlineKeyboardMarkup:
    return build_keyboard(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Открыть Basic →" if mobile_connect_url and mobile_connect_url != connect_url else "Открыть инструкцию →",
                    web_app=WebAppInfo(
                        url=connect_url,
                    ),
                )
            ],
            *([[InlineKeyboardButton(
                text="Открыть Mobile →",
                web_app=WebAppInfo(url=mobile_connect_url),
            )]] if mobile_connect_url and mobile_connect_url != connect_url else []),
            [
                InlineKeyboardButton(
                    text="← Назад",
                    callback_data=f"device:{device_id}",
                )
            ],
        ]
    )
