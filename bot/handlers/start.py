import httpx
from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from api.backend import backend_post
from ui.home import build_home_text
from ui.main import main_menu


router = Router(
    name="start",
)


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
            "⚠️ Сервис временно недоступен.\n"
            "Попробуйте немного позже."
        )
        return

    if response.status_code not in (201, 409):
        await message.answer(
            "Не удалось загрузить профиль."
        )
        return

    text = build_home_text(
        telegram_user.first_name,
        is_new_user=response.status_code == 201,
    )

    await message.answer(
        text,
        reply_markup=main_menu,
    )