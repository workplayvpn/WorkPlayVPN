from aiogram import F, Router
from aiogram.types import CallbackQuery

from ui.common import build_back_to_main_keyboard
from ui.helpers import edit_screen


router = Router(
    name="help",
)


@router.callback_query(
    F.data == "help"
)
async def show_help(
    callback: CallbackQuery,
) -> None:
    await callback.answer()

    text = (
        "❓ Помощь\n\n"
        "1. Выберите тариф.\n"
        "2. Активируйте подписку.\n"
        "3. Откройте «Мои устройства».\n"
        "4. Подключите устройство.\n"
        "5. Импортируйте полученную "
        "VLESS-ссылку в VPN-клиент.\n\n"
        "Поддержка и подробные инструкции "
        "будут добавлены позже."
    )

    await edit_screen(
        callback,
        text,
        build_back_to_main_keyboard(),
    )