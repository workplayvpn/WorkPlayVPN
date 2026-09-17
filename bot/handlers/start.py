import httpx
from aiogram import Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import CommandStart
from aiogram.types import FSInputFile, Message

from api.backend import backend_post
from ui.home import build_home_text
from ui.main import main_menu


router = Router(
    name="start",
)

_welcome_photo_file_id: str | None = None


async def send_home_message(
    message: Message,
    *,
    text: str,
) -> None:
    global _welcome_photo_file_id

    photo = (
        _welcome_photo_file_id
        or FSInputFile("assets/welcome.png")
    )

    try:
        sent_message = await message.answer_photo(
            photo=photo,
            caption=text,
            reply_markup=main_menu,
        )
    except TelegramBadRequest:
        if _welcome_photo_file_id is None:
            raise

        _welcome_photo_file_id = None
        sent_message = await message.answer_photo(
            photo=FSInputFile("assets/welcome.png"),
            caption=text,
            reply_markup=main_menu,
        )

    if sent_message.photo:
        _welcome_photo_file_id = sent_message.photo[-1].file_id


@router.message(CommandStart())
async def handle_start(
    message: Message,
) -> None:
    telegram_user = message.from_user

    if telegram_user is None:
        return

    payload = {
        "telegram_id": telegram_user.id,
        "username": telegram_user.username,
        "first_name": telegram_user.first_name,
    }

    try:
        response = await backend_post(
            "/users",
            payload,
        )
    except httpx.RequestError:
        await message.answer(
            "⚠️ Work&PlayVPN временно недоступен.\n\n"
            "Попробуйте открыть бот немного позже."
        )
        return

    if response.status_code not in (201, 409):
        await message.answer(
            "⚠️ Не удалось загрузить профиль.\n\n"
            "Попробуйте отправить /start ещё раз."
        )
        return

    text = build_home_text(
        telegram_user.first_name,
        is_new_user=response.status_code == 201,
    )

    try:
        await send_home_message(
            message,
            text=text,
        )
    except (OSError, RuntimeError, TelegramBadRequest):
        await message.answer(
            text,
            reply_markup=main_menu,
        )
