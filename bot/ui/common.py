from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)


def build_back_to_main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="← На главную",
                    callback_data="main_menu",
                )
            ]
        ]
    )
