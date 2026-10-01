from ui.media import get_screen_photo
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import (
    CallbackQuery,
    InputFile,
    InputMediaPhoto,
    Message,
)


async def edit_screen(
    callback: CallbackQuery,
    text: str,
    reply_markup=None,
    *,
    photo: str | InputFile | None = None,
) -> Message | None:
    if callback.message is None:
        return

    if photo is None:
        photo = get_screen_photo(callback.data, text)

    if len(text) > 1024:
        await callback.message.edit_media(
            media=InputMediaPhoto(media=photo, caption=text.split("\n", 1)[0]),
        )
        return await callback.message.answer(text, reply_markup=reply_markup)

    try:
        if photo is not None:
            return await callback.message.edit_media(
                media=InputMediaPhoto(
                    media=photo,
                    caption=text,
                ),
                reply_markup=reply_markup,
            )

        if getattr(callback.message, "photo", None):
            return await callback.message.edit_caption(
                caption=text,
                reply_markup=reply_markup,
            )
        else:
            return await callback.message.edit_text(
                text,
                reply_markup=reply_markup,
            )
    except TelegramBadRequest as exc:
        if "message is not modified" in str(exc):
            return callback.message

        raise
