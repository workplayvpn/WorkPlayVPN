from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)


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