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
                text="🔑 Моя подписка",
                callback_data="subscription",
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
                text="🌍 Сменить регион",
                callback_data="change_region",
            ),
        ],
        [
            InlineKeyboardButton(
                text="📄 Документы",
                url="https://workplayvpn.ru/#documents",
            ),
            InlineKeyboardButton(
                text="🛟 Помощь",
                callback_data="help",
            ),
        ],
    ]
)
