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
                    text="Продолжить к оплате →",
                    callback_data=f"pay_plan:{plan_code}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="← Изменить тариф",
                    callback_data="plans",
                )
            ],
        ]
    )


def build_payment_keyboard(
    confirmation_url: str,
    payment_id: int,
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Оплатить безопасно →",
                    url=confirmation_url,
                )
            ],
            [
                InlineKeyboardButton(
                    text="← К тарифам",
                    callback_data="plans",
                )
            ],
        ]
    )
