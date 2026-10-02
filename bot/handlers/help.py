from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, WebAppInfo
from config import mini_app_url
from ui.common import build_keyboard
from ui.helpers import edit_screen
router = Router(name="help")

@router.callback_query(F.data.in_({"help", "report_problem"}))
async def show_help(callback: CallbackQuery):
    await callback.answer()
    def link(view): return f"{mini_app_url}{'&' if '?' in mini_app_url else '?'}view={view}"
    keyboard=build_keyboard(inline_keyboard=[
        [InlineKeyboardButton(text="📚 База знаний", web_app=WebAppInfo(url=link("help")))],
        [InlineKeyboardButton(text="🛟 Сообщить о проблеме", web_app=WebAppInfo(url=link("support")))],
        [InlineKeyboardButton(text="💬 Написать в поддержку", url="https://t.me/workplayvpnteam")],
        [InlineKeyboardButton(text="← На главную",callback_data="main_menu")]])
    await edit_screen(callback,"🛟 Помощь Work&PlayVPN\n\nИнструкции по Happ, подпискам, устройствам и реферальной программе — в базе знаний.\n\nЕсли инструкция не помогла, отправьте обращение: получите номер и сможете следить за статусом в Mini App.\n\nНе передавайте ключ подписки, пароли, CVV или коды из SMS.",keyboard)
