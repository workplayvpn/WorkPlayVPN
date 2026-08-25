from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)


def build_payment_keyboard(
    confirmation_url: str,
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💳 Перейти к оплате",
                    url=confirmation_url,
                )
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ К тарифам",
                    callback_data="plans",
                )
            ],
        ]
    )