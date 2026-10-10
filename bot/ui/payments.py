from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)

from ui.common import build_keyboard

PURCHASE_TERMS_TEXT = (
    "Перед оплатой ознакомьтесь с документами по кнопкам ниже. "
    "Нажимая кнопку перехода к оплате, вы принимаете публичную оферту "
    "и правила использования и ознакомлены с условиями возврата."
)


def purchase_document_rows():
    return [
        [InlineKeyboardButton(text="Публичная оферта ↗", url="https://workplayvpn.ru/offer.html")],
        [InlineKeyboardButton(text="Правила использования ↗", url="https://workplayvpn.ru/rules.html"),
         InlineKeyboardButton(text="Условия возврата ↗", url="https://workplayvpn.ru/refund.html")],
    ]



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
            *purchase_document_rows(),
            [
                InlineKeyboardButton(
                    text="← Изменить тариф",
                    callback_data=(
                        f"plans_tier:{source[6:]}:renew" if source in ("renew_basic", "renew_mobile") else "subscription_plans"
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
            *purchase_document_rows(),
            [
                InlineKeyboardButton(
                    text="← К лимиту" if source in ("slots", "slots_basic", "slots_mobile") else "← К тарифам",
                    callback_data=(
                        f"device_slots:{source[6:]}" if source in ("slots_basic", "slots_mobile") else "device_slots" if source == "slots" else f"plans_tier:{source[6:]}:renew" if source in ("renew_basic", "renew_mobile") else "subscription_plans"
                        if source == "subscription"
                        else "plans"
                    ),
                )
            ],
        ]
    )
