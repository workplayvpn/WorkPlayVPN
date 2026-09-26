from aiogram.types import (
    CopyTextButton,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    WebAppInfo,
)

from config import mini_app_devices_url, mini_app_url


def build_subscription_keyboard(
    *,
    active: bool,
    connect_url: str | None = None,
    mobile_connect_url: str | None = None,
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
            *([[InlineKeyboardButton(
                text="📱 Подключить Mobile",
                web_app=WebAppInfo(url=mobile_connect_url),
            )]] if mobile_connect_url and mobile_connect_url != connect_url else []),
            [
                InlineKeyboardButton(
                    text="⏳ Продлить",
                    callback_data="subscription_plans",
                ),
                InlineKeyboardButton(
                    text="＋ Устройство",
                    web_app=WebAppInfo(
                        url=mini_app_devices_url,
                    ),
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🛟 Сообщить о проблеме",
                    url="https://t.me/workplayvpnteam",
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


def build_subscription_secret_keyboard(
    copy_value: str | None = None,
    mobile_copy_value: str | None = None,
) -> InlineKeyboardMarkup:
    rows = []

    if copy_value:
        rows.append(
            [
                InlineKeyboardButton(
                    text="📋 Скопировать основную ссылку",
                    copy_text=CopyTextButton(
                        text=copy_value,
                    ),
                )
            ]
        )

    if mobile_copy_value and mobile_copy_value != copy_value:
        rows.append([InlineKeyboardButton(
            text="📋 Скопировать Mobile",
            copy_text=CopyTextButton(text=mobile_copy_value),
        )])

    rows.append(
        [
            InlineKeyboardButton(
                text="← К подписке",
                callback_data="subscription",
            )
        ]
    )

    return InlineKeyboardMarkup(
        inline_keyboard=rows,
    )
