import re
import httpx
from aiogram import Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import CommandStart
from aiogram.filters.command import CommandObject
from aiogram.types import FSInputFile, Message, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from config import mini_app_url

from api.backend import backend_post
from ui.home import build_home_text
from ui.main import main_menu
from ui.media import (
    get_welcome_photo,
    remember_welcome_photo,
    reset_welcome_photo,
)


router = Router(
    name="start",
)

async def send_home_message(
    message: Message,
    *,
    text: str,
) -> None:
    try:
        sent_message = await message.answer_photo(
            photo=get_welcome_photo(),
            caption=text,
            reply_markup=main_menu,
        )
    except TelegramBadRequest:
        reset_welcome_photo()
        sent_message = await message.answer_photo(
            photo=FSInputFile("assets/welcome.png"),
            caption=text,
            reply_markup=main_menu,
        )

    remember_welcome_photo(sent_message)


@router.message(CommandStart())
async def handle_start(
    message: Message,
    command: CommandObject,
) -> None:
    telegram_user = message.from_user

    if telegram_user is None:
        return

    # Returning from the payment page only reveals the existing chat.
    if command.args == "payment_return" and message.chat.type == "private":
        return

    payload = {
        "telegram_id": telegram_user.id,
        "username": telegram_user.username,
        "first_name": telegram_user.first_name,
    }

    match = re.fullmatch(r"ref_([a-f0-9]{24})", command.args or "")
    if match:
        payload["referral_code"] = match.group(1)

    try:
        response = await backend_post(
            "/users",
            payload,
        )
    except httpx.RequestError:
        await message.answer(
            "⚠️ Work&PlayVPN временно недоступен.\n\n"
            "Попробуйте открыть бот немного позже."
        )
        return

    if response.status_code not in (201, 409):
        await message.answer(
            "⚠️ Не удалось загрузить профиль.\n\n"
            "Попробуйте отправить /start ещё раз."
        )
        return

    gift_match = re.fullmatch(r"gift_([A-Z2-7]{24})", command.args or "")
    if gift_match and message.chat.type == "private":
        code = gift_match.group(1)
        await message.answer(
            "🎁 Вам подарили Work&PlayVPN!\n\nОткройте подарок, проверьте тип и срок подписки и подтвердите активацию. Срок начнётся после активации; действующая подписка того же типа будет продлена.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(
                text="🎁 Открыть подарок", web_app=WebAppInfo(
                    url=f"{mini_app_url}{'&' if '?' in mini_app_url else '?'}view=gifts&gift_code={code}"))]]))
        return

    text = build_home_text(
        telegram_user.first_name,
        is_new_user=response.status_code == 201,
    )

    try:
        await send_home_message(
            message,
            text=text,
        )
    except (OSError, RuntimeError, TelegramBadRequest):
        await message.answer(
            text,
            reply_markup=main_menu,
        )
