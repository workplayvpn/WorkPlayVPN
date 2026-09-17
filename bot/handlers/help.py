from aiogram import F, Router
from aiogram.types import CallbackQuery

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from ui.helpers import edit_screen


router = Router(
    name="help",
)


@router.callback_query(
    F.data.in_({"help", "report_problem"})
)
async def show_help(
    callback: CallbackQuery,
) -> None:
    await callback.answer()

    text = (
        "🛟 Как подключиться\n\n"
        "1. Откройте приложение Work&PlayVPN.\n"
        "2. Выберите и оплатите тариф.\n"
        "3. Нажмите «Подключить устройство».\n"
        "4. Выберите доступный сервер.\n"
        "5. Следуйте инструкции по установке HAPP.\n\n"
        "Ссылка подключения создаётся отдельно "
        "для каждого устройства. Не передавайте "
        "её другим людям.\n\n"
        "Если данные не обновились, вернитесь "
        "на главную и откройте раздел ещё раз.\n\n"
        "Поддержка в Telegram: @workplayvpnteam\n\n"
        "Не отправляйте ключ подписки, пароль "
        "или платёжные данные."
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💬 Написать в поддержку",
                    url="https://t.me/workplayvpnteam",
                )
            ],
            [
                InlineKeyboardButton(
                    text="← На главную",
                    callback_data="main_menu",
                )
            ],
        ]
    )

    await edit_screen(
        callback,
        text,
        keyboard,
    )
