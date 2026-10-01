from aiogram.types import (
    InlineKeyboardButton,
    WebAppInfo,
)

from config import mini_app_devices_url, mini_app_url, mini_app_referrals_url
from ui.common import build_keyboard


main_menu = build_keyboard(
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
                text="🔑 Мои подписки",
                callback_data="subscription",
            ),
        ],
        [
            InlineKeyboardButton(
                text="💎 Каталог подписок",
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
                web_app=WebAppInfo(
                    url=mini_app_devices_url,
                ),
            ),
            InlineKeyboardButton(
                text="🌍 Сменить регион",
                callback_data="change_region",
            ),
        ],
        [InlineKeyboardButton(text="🤝 Реферальная программа",
            web_app=WebAppInfo(url=mini_app_referrals_url))],
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
