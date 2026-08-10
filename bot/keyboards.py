from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


main_menu = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text="💳 Тарифы",
                callback_data="plans",
            ),
            InlineKeyboardButton(
                text="👤 Мой профиль",
                callback_data="profile",
            ),
        ],
        [
            InlineKeyboardButton(
                text="🌍 Страны",
                callback_data="locations",
            ),
            InlineKeyboardButton(
                text="❓ Помощь",
                callback_data="help",
            ),
        ],
    ]
)