from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery


async def edit_screen(
    callback: CallbackQuery,
    text: str,
    reply_markup=None,
) -> None:
    if callback.message is None:
        return

    try:
        await callback.message.edit_text(
            text,
            reply_markup=reply_markup,
        )
    except TelegramBadRequest as exc:
        if "message is not modified" in str(exc):
            return

        raise