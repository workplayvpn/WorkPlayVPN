from aiogram import F, Router
from api.backend import backend_get
from aiogram.types import CallbackQuery, CopyTextButton, InlineKeyboardButton, WebAppInfo
from config import mini_app_url
from ui.common import build_keyboard
from ui.helpers import edit_screen
router = Router(name="help")

@router.callback_query(F.data.in_({"help", "report_problem"}))
async def show_help(callback: CallbackQuery):
    if callback.message is None or callback.message.chat.type != "private":
        await callback.answer("Ключ помощи доступен только в личном чате с ботом.", show_alert=True)
        return
    await callback.answer()
    def link(view): return f"{mini_app_url}{'&' if '?' in mini_app_url else '?'}view={view}"
    keyboard=build_keyboard(inline_keyboard=[
        [InlineKeyboardButton(text="📚 База знаний", web_app=WebAppInfo(url=link("help")))],
        [InlineKeyboardButton(text="🛟 Сообщить о проблеме", web_app=WebAppInfo(url=link("support")))],
        [InlineKeyboardButton(text="💬 Написать в поддержку", url="https://t.me/workplayvpnteam")],
        [InlineKeyboardButton(text="← На главную",callback_data="main_menu")]])
    key_text = "Не удалось получить ключ. Попробуйте открыть раздел ещё раз."
    try:
        response = await backend_get(f"/internal/support/access-key/{callback.from_user.id}")
        response.raise_for_status()
        key_text = response.json()["key"]
        keyboard.inline_keyboard.insert(0, [InlineKeyboardButton(text="📋 Скопировать ключ помощи", copy_text=CopyTextButton(text=key_text))])
    except Exception:
        pass
    await edit_screen(callback,
        "🛟 Помощь Work&PlayVPN\n\n"
        "Ваш персональный ключ помощи:\n" + key_text + "\n\n"
        "Скопируйте ключ и введите его на экране входа в центр помощи — на сайте или в Mini App. "
        "Ключ открывает только помощь; не передавайте его посторонним.\n\n"
        "В базе знаний — инструкции по Happ, подпискам, устройствам и рефералам. "
        "Если подсказки не помогли, создайте обращение и следите за ответом в Mini App.\n\n"
        "Не передавайте ключ подписки, пароли, CVV или коды из SMS.", keyboard)
