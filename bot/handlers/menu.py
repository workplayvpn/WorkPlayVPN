from aiogram import F, Router
from aiogram.types import CallbackQuery

from ui.main import main_menu
from ui.helpers import edit_screen


router = Router(
    name="menu",
)


@router.callback_query(
    F.data == "main_menu"
)
async def show_main_menu(
    callback: CallbackQuery,
) -> None:
    await callback.answer()

    await edit_screen(
        callback,
        "🛡 Work&PlayVPN\n\n"
        "Главное меню\n\n"
        "Выберите нужный раздел:",
        main_menu,
    )