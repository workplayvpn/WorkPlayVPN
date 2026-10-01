from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from ui.common import build_keyboard


def build_documents_keyboard() -> InlineKeyboardMarkup:
    return build_keyboard(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📃 Публичная оферта",
                    callback_data="document:offer",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔐 Конфиденциальность",
                    callback_data="document:privacy",
                )
            ],
            [
                InlineKeyboardButton(
                    text="↩️ Условия возврата",
                    callback_data="document:refund",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🏢 Реквизиты",
                    callback_data="document:details",
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


def build_document_back_keyboard() -> InlineKeyboardMarkup:
    return build_keyboard(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="← К документам",
                    callback_data="documents",
                )
            ]
        ]
    )
