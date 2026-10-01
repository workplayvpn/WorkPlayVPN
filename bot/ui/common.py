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


_PRIMARY_CALLBACKS = frozenset({
    "subscription_key", "subscription_qr", "change_region", "plans",
})
_PRIMARY_PREFIXES = ("device_key:", "device_link:", "pay_plan:")
_DANGER_PREFIXES = ("remove_device:", "confirm_remove_device:")


def build_keyboard(
    *, inline_keyboard: list[list[InlineKeyboardButton]],
) -> InlineKeyboardMarkup:
    """Keep one action per row and consistent accents across bot screens."""
    rows = []
    for row in inline_keyboard:
        for button in row:
            callback = button.callback_data or ""
            style = button.style
            if callback.startswith(_DANGER_PREFIXES):
                style = "danger"
            elif (
                button.web_app is not None
                or button.copy_text is not None
                or callback in _PRIMARY_CALLBACKS
                or callback.startswith(_PRIMARY_PREFIXES)
            ):
                style = "primary"
            rows.append([button.model_copy(update={"style": style})])
    return InlineKeyboardMarkup(inline_keyboard=rows)
