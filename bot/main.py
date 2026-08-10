import asyncio
import os

import httpx
from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.types import Message


telegram_bot_token = os.environ["TELEGRAM_BOT_TOKEN"]
backend_url = os.getenv(
    "BACKEND_URL",
    "http://backend:8000",
)

dispatcher = Dispatcher()


@dispatcher.message(CommandStart())
async def handle_start(message: Message) -> None:
    telegram_user = message.from_user

    if telegram_user is None:
        return

    payload = {
        "telegram_id": telegram_user.id,
        "username": telegram_user.username,
        "first_name": telegram_user.first_name,
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{backend_url}/users",
                json=payload,
            )
    except httpx.RequestError:
        await message.answer(
            "Сервис временно недоступен. Попробуйте немного позже."
        )
        return

    if response.status_code == 201:
        await message.answer(
            f"Добро пожаловать, {telegram_user.first_name}! "
            "Ваш профиль Work&PlayVPN создан."
        )
        return

    if response.status_code == 409:
        await message.answer(
            f"С возвращением, {telegram_user.first_name}!"
        )
        return

    await message.answer(
        "Не удалось создать профиль. Попробуйте немного позже."
    )


async def main() -> None:
    bot = Bot(token=telegram_bot_token)

    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dispatcher.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())