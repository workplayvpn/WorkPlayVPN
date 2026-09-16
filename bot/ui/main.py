from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    WebAppInfo,
)

from config import mini_app_url


main_menu = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text="🚀 Открыть Work&PlayVPN",
                web_app=WebAppInfo(
                    url=mini_app_url,
                ),
            ),
        ],
        [
            InlineKeyboardButton(
                text="💎 Тарифы",
                callback_data="plans",
            ),
            InlineKeyboardButton(
                text="👤 Профиль",
                callback_data="profile",
            ),
        ],
        [
            InlineKeyboardButton(
                text="📱 Устройства",
                callback_data="devices",
            ),
            InlineKeyboardButton(
                text="🌍 Серверы",
                callback_data="locations",
            ),
        ],
        [
            InlineKeyboardButton(
                text="🛟 Помощь",
                callback_data="help",
            ),
        ],
    ]
)
