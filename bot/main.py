import asyncio

from aiogram import Bot, Dispatcher

from config import telegram_bot_token
from handlers.devices import router as devices_router
from handlers.help import router as help_router
from handlers.locations import router as locations_router
from handlers.menu import router as menu_router
from handlers.plans import router as plans_router
from handlers.profile import router as profile_router
from handlers.start import router as start_router


dispatcher = Dispatcher()

dispatcher.include_router(
    start_router
)

dispatcher.include_router(
    menu_router
)

dispatcher.include_router(
    plans_router
)

dispatcher.include_router(
    profile_router
)

dispatcher.include_router(
    locations_router
)

dispatcher.include_router(
    devices_router
)

dispatcher.include_router(
    help_router
)


async def main() -> None:
    bot = Bot(
        token=telegram_bot_token
    )

    try:
        await bot.delete_webhook(
            drop_pending_updates=True
        )

        await dispatcher.start_polling(
            bot
        )

    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())