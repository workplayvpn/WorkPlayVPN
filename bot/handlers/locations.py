import httpx
from aiogram import F, Router
from aiogram.types import CallbackQuery

from api.backend import backend_get
from ui.common import build_back_to_main_keyboard
from ui.main import main_menu
from ui.helpers import edit_screen


router = Router(
    name="locations",
)


@router.callback_query(
    F.data == "locations"
)
async def show_locations(
    callback: CallbackQuery,
) -> None:
    await callback.answer()

    try:
        response = await backend_get(
            "/catalog/locations"
        )
    except httpx.RequestError:
        await edit_screen(
            callback,
            "⚠️ Не удалось загрузить локации.",
            main_menu,
        )
        return

    if response.status_code != 200:
        await edit_screen(
            callback,
            "⚠️ Не удалось загрузить локации.",
            main_menu,
        )
        return

    lines = [
        "🌍 Локации Work&PlayVPN",
        "",
    ]

    for location in response.json():
        lines.append(
            f"• {location['name']}"
        )

    lines.extend(
        [
            "",
            "Доступность серверов "
            "будет расширяться постепенно.",
        ]
    )

    await edit_screen(
        callback,
        "\n".join(lines),
        build_back_to_main_keyboard(),
    )