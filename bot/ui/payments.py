from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)

from ui.common import build_keyboard


def build_payment_confirmation_keyboard(
    plan_code: str,
    *,
    source: str = "main",
) -> InlineKeyboardMarkup:
    return build_keyboard(
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
    return build_keyboard(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Оплатить безопасно →",
                    style="primary",
                    url=confirmation_url,
                )
            ],
            [
                InlineKeyboardButton(
                    text="← К лимиту" if source == "slots" else "← К тарифам",
                    callback_data=(
                        "device_slots" if source == "slots" else "subscription_plans"
                        if source == "subscription"
                        else "plans"
                    ),
                )
            ],
        ]
    )
