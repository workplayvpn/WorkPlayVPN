from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)


def build_payment_confirmation_keyboard(
    plan_code: str,
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💳 Перейти к оплате",
                    callback_data=f"pay_plan:{plan_code}",
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
