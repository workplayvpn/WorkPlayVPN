import asyncio
import os

import httpx
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, Message

from keyboards import main_menu


telegram_bot_token = os.environ["TELEGRAM_BOT_TOKEN"]
backend_url = os.getenv(
    "BACKEND_URL",
    "http://backend:8000",
)

dispatcher = Dispatcher()


async def backend_get(path: str) -> httpx.Response:
    async with httpx.AsyncClient(timeout=10.0) as client:
        return await client.get(f"{backend_url}{path}")


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
        text = (
            f"Добро пожаловать, {telegram_user.first_name}! "
            "Ваш профиль Work&PlayVPN создан."
        )
    elif response.status_code == 409:
        text = f"С возвращением, {telegram_user.first_name}!"
    else:
        await message.answer(
            "Не удалось загрузить профиль. Попробуйте немного позже."
        )
        return

    await message.answer(
        text,
        reply_markup=main_menu,
    )


@dispatcher.callback_query(F.data == "plans")
async def show_plans(callback: CallbackQuery) -> None:
    await callback.answer()

    try:
        response = await backend_get("/catalog/plans")
    except httpx.RequestError:
        await callback.message.answer(
            "Не удалось загрузить тарифы.",
            reply_markup=main_menu,
        )
        return

    if response.status_code != 200:
        await callback.message.answer(
            "Не удалось загрузить тарифы.",
            reply_markup=main_menu,
        )
        return

    lines = ["💳 Тарифы Work&PlayVPN", ""]

    for plan in response.json():
        price = str(plan["price_amount"]).removesuffix(".00")
        devices = plan["device_limit"]

        if plan["code"] == "trial_3d":
            lines.append(
                f"🎁 {plan['name']}: 3 дня, "
                f"{devices} устройство, бесплатно"
            )
        else:
            lines.append(
                f"• {plan['name']}: {price} ₽, "
                f"до {devices} устройств"
            )

    lines.extend(
        [
            "",
            "➕ Дополнительное устройство навсегда: 249 ₽",
        ]
    )

    await callback.message.answer(
        "\n".join(lines),
        reply_markup=main_menu,
    )


@dispatcher.callback_query(F.data == "profile")
async def show_profile(callback: CallbackQuery) -> None:
    await callback.answer()

    try:
        response = await backend_get(
            f"/users/{callback.from_user.id}"
        )
    except httpx.RequestError:
        await callback.message.answer(
            "Не удалось загрузить профиль.",
            reply_markup=main_menu,
        )
        return

    if response.status_code != 200:
        await callback.message.answer(
            "Профиль не найден. Отправьте /start.",
            reply_markup=main_menu,
        )
        return

    user = response.json()
    username = (
    f"@{user['username']}"
    if user["username"]
    else "не указан"
)

    text = (
        "👤 Ваш профиль\n\n"
        f"Telegram ID: {user['telegram_id']}\n"
        f"Username: {username}\n"
        f"Дополнительных устройств: "
        f"{user['extra_device_slots']}\n"
        "Подписка: пока не оформлена"
    )

    await callback.message.answer(
        text,
        reply_markup=main_menu,
    )


@dispatcher.callback_query(F.data == "locations")
async def show_locations(callback: CallbackQuery) -> None:
    await callback.answer()

    try:
        response = await backend_get("/catalog/locations")
    except httpx.RequestError:
        await callback.message.answer(
            "Не удалось загрузить список стран.",
            reply_markup=main_menu,
        )
        return

    if response.status_code != 200:
        await callback.message.answer(
            "Не удалось загрузить список стран.",
            reply_markup=main_menu,
        )
        return

    lines = ["🌍 Доступные страны", ""]

    for location in response.json():
        lines.append(f"• {location['name']}")

    await callback.message.answer(
        "\n".join(lines),
        reply_markup=main_menu,
    )


@dispatcher.callback_query(F.data == "help")
async def show_help(callback: CallbackQuery) -> None:
    await callback.answer()

    await callback.message.answer(
        "❓ Помощь\n\n"
        "Выберите тариф, оформите подписку и получите "
        "доступ к Work&PlayVPN.\n\n"
        "Поддержка будет добавлена на следующем этапе.",
        reply_markup=main_menu,
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