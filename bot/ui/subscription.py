from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    WebAppInfo,
)

from config import mini_app_url


def build_subscription_keyboard(
    *,
    active: bool,
    connect_url: str | None = None,
) -> InlineKeyboardMarkup:
    if not active:
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="💎 Выбрать тариф",
                        callback_data="plans",
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="🚀 Открыть Work&PlayVPN",
                        web_app=WebAppInfo(url=mini_app_url),
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="← На главную",
                        callback_data="main_menu",
                    )
                ],
            ]
        )

    instruction_button = InlineKeyboardButton(
        text="📖 Инструкция",
        web_app=WebAppInfo(
            url=connect_url or mini_app_url,
        ),
    )

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔑 Показать ключ",
                    callback_data="subscription_key",
                ),
                InlineKeyboardButton(
                    text="📷 QR-код",
                    callback_data="subscription_qr",
                ),
            ],
            [instruction_button],
            [
                InlineKeyboardButton(
                    text="⏳ Продлить",
                    callback_data="plans",
                ),
                InlineKeyboardButton(
                    text="＋ Устройство",
                    callback_data="add_device",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🛟 Сообщить о проблеме",
                    callback_data="report_problem",
                )
            ],
            [
                InlineKeyboardButton(
                    text="← На главную",
                    callback_data="main_menu",
                )
            ],
        ]
    )


def build_subscription_secret_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="← К подписке",
                    callback_data="subscription",
                )
            ]
        ]
    )
