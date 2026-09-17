from aiogram import F, Router
from aiogram.types import CallbackQuery

from ui.helpers import edit_screen
from ui.home import build_home_text
from ui.main import main_menu
from ui.media import get_welcome_photo, remember_welcome_photo


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

    telegram_user = callback.from_user

    message = await edit_screen(
        callback,
        build_home_text(
            telegram_user.first_name,
        ),
        main_menu,
        photo=get_welcome_photo(),
    )

    if message is not None:
        remember_welcome_photo(message)
