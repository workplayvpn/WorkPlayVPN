from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


main_menu = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text="💳 Тарифы",
                callback_data="plans",
            ),
            InlineKeyboardButton(
                text="👤 Профиль",
                callback_data="profile",
            ),
        ],
        [
            InlineKeyboardButton(
                text="📱 Мои устройства",
                callback_data="devices",
            ),
        ],
        [
            InlineKeyboardButton(
                text="🌍 Локации",
                callback_data="locations",
            ),
            InlineKeyboardButton(
                text="❓ Помощь",
                callback_data="help",
            ),
        ],
    ]
)


def build_plans_keyboard(
    plans: list[dict],
) -> InlineKeyboardMarkup:
    rows = []

    for plan in plans:
        if plan["code"] == "trial_3d":
            text = "🎁 Пробный — бесплатно"
        else:
            price = str(
                plan["price_amount"]
            ).removesuffix(".00")

            text = f"{plan['name']} — {price} ₽"

        rows.append(
            [
                InlineKeyboardButton(
                    text=text,
                    callback_data=(
                        f"select_plan:{plan['code']}"
                    ),
                )
            ]
        )

    rows.append(
        [
            InlineKeyboardButton(
                text="⬅️ Главное меню",
                callback_data="main_menu",
            )
        ]
    )

    return InlineKeyboardMarkup(
        inline_keyboard=rows,
    )


def build_devices_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="➕ Подключить устройство",
                    callback_data="add_device",
                )
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ Главное меню",
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
                text="➕ Подключить устройство",
                callback_data="add_device",
            )
        ]
    )

    rows.append(
        [
            InlineKeyboardButton(
                text="⬅️ Главное меню",
                callback_data="main_menu",
            )
        ]
    )

    return InlineKeyboardMarkup(
        inline_keyboard=rows,
    )


def build_device_keyboard(
    device_id: int,
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔗 Получить подключение",
                    callback_data=f"device_link:{device_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="⚙️ Управление устройством",
                    callback_data=f"device_manage:{device_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ Мои устройства",
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
                    text="🗑 Отвязать устройство",
                    callback_data=f"remove_device:{device_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ Назад",
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
                    text="✅ Да, отвязать",
                    callback_data=(
                        f"confirm_remove_device:{device_id}"
                    ),
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ Отмена",
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
        rows.append(
            [
                InlineKeyboardButton(
                    text=location["name"],
                    callback_data=(
                        f"device_location:{location['code']}"
                    ),
                )
            ]
        )

    rows.append(
        [
            InlineKeyboardButton(
                text="⬅️ Мои устройства",
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
                    text="🚀 Подключить это устройство",
                    url=activation_url,
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔄 Проверить устройства",
                    callback_data="devices",
                )
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ Назад",
                    callback_data="add_device",
                )
            ],
        ]
    )


def build_back_to_main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⬅️ Главное меню",
                    callback_data="main_menu",
                )
            ]
        ]
    )