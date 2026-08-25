import httpx
from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from api.backend import backend_post
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

    if response.status_code == 201:
        greeting = (
            f"Добро пожаловать, "
            f"{telegram_user.first_name}!"
        )
    elif response.status_code == 409:
        greeting = (
            f"С возвращением, "
            f"{telegram_user.first_name}!"
        )
    else:
        await message.answer(
            "Не удалось загрузить профиль."
        )
        return

    text = (
        "🛡 Work&PlayVPN\n\n"
        f"{greeting}\n\n"
        "Быстрый и безопасный доступ "
        "к интернету.\n\n"
        "Выберите нужный раздел:"
    )

    await message.answer(
        text,
        reply_markup=main_menu,
    )