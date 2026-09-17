from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)


def build_payment_confirmation_keyboard(
    plan_code: str,
    *,
    source: str = "main",
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Продолжить к оплате →",
                    callback_data=(
                        f"pay_plan:{plan_code}:{source}"
                    ),
                )
            ],
            [
                InlineKeyboardButton(
                    text="← Изменить тариф",
                    callback_data=(
                        "subscription_plans"
                        if source == "subscription"
                        else "plans"
                    ),
                )
            ],
        ]
    )


def build_payment_keyboard(
    confirmation_url: str,
    payment_id: int,
    *,
    source: str = "main",
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
                    callback_data=(
                        "subscription_plans"
                        if source == "subscription"
                        else "plans"
                    ),
                )
            ],
        ]
    )
