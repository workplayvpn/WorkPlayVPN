import asyncio

from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.types import (
    BotCommand,
    MenuButtonWebApp,
    WebAppInfo,
)

from config import (
    mini_app_url,
    telegram_bot_token,
    telegram_proxy_url,
)
from handlers.devices import router as devices_router
from handlers.help import router as help_router
from handlers.locations import router as locations_router
from handlers.menu import router as menu_router
from handlers.plans import router as plans_router
from handlers.profile import router as profile_router
from handlers.subscription import router as subscription_router
from handlers.documents import router as documents_router
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
    subscription_router
)

dispatcher.include_router(
    documents_router
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


def create_bot() -> Bot:
    if telegram_proxy_url:
        session = AiohttpSession(
            proxy=telegram_proxy_url,
        )

        return Bot(
            token=telegram_bot_token,
            session=session,
        )

    return Bot(
        token=telegram_bot_token,
    )


async def main() -> None:
    bot = create_bot()

    try:
        await bot.delete_webhook(
            drop_pending_updates=True
        )

        await bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(
                text="Work&PlayVPN",
                web_app=WebAppInfo(
                    url=mini_app_url,
                ),
            )
        )

        await bot.set_my_commands(
            [
                BotCommand(
                    command="start",
                    description="Открыть главное меню",
                ),
            ]
        )

        await bot.set_my_short_description(
            "Защищённый интернет без сложных настроек."
        )

        await bot.set_my_description(
            "Work&PlayVPN помогает быстро подключить "
            "защищённый доступ к интернету на телефоне, "
            "планшете или компьютере. Выберите тариф, "
            "добавьте устройство и следуйте инструкции."
        )

        await dispatcher.start_polling(
            bot
        )

    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
