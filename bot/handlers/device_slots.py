import httpx
from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton
from api.backend import backend_get, backend_post
from ui.common import build_keyboard
from ui.helpers import edit_screen
from ui.payments import build_payment_keyboard

router = Router(name="device_slots")


@router.callback_query(F.data == "device_slots")
async def show_slots(callback: CallbackQuery):
    await callback.answer()
    try:
        response = await backend_get(f"/payments/device-slots/{callback.from_user.id}/offers")
        if response.status_code != 200:
            await edit_screen(callback, "Для добавления лимита нужна активная подписка Basic или Mobile.",
                build_keyboard(inline_keyboard=[[InlineKeyboardButton(text="← Назад", callback_data="subscription")]]))
            return
        data = response.json()
        rows = [[InlineKeyboardButton(text=f"+{o['slots']} · {o['price_amount'].removesuffix('.00')} ₽ · станет {o['new_limit']}",
                callback_data=f"buy_slots:{o['code']}")] for o in data['offers']]
        rows.append([InlineKeyboardButton(text="← Назад", callback_data="subscription")])
        await edit_screen(callback, f"📱 Добавить лимит устройств\n\nСейчас доступно: {data['total_limit']} слотов.\nВыберите +1, +2 или +3 слота. Лимит общий для Basic и Mobile.\nРазовая покупка: слоты сохраняются при продлении, но для подключения нужна действующая подписка.", build_keyboard(inline_keyboard=rows))
    except httpx.RequestError:
        await edit_screen(callback, "⚠️ Не удалось загрузить лимит. Попробуйте ещё раз.", build_keyboard(inline_keyboard=[[InlineKeyboardButton(text="Повторить", callback_data="device_slots")]]))


@router.callback_query(F.data.startswith("buy_slots:"))
async def buy_slots(callback: CallbackQuery):
    await callback.answer()
    code = callback.data.split(":", 1)[1]
    if code not in {"device_slots_1", "device_slots_2", "device_slots_3"}:
        await show_slot_error(callback)
        return
    try:
        response = await backend_post("/payments", {"telegram_id": callback.from_user.id,
            "plan_code": code, "idempotency_key": f"slots-{callback.id}"})
        if response.status_code != 201:
            await show_slot_error(callback)
            return
        payment = response.json()
        await edit_screen(callback, f"💳 Добавление лимита устройств\n\nСумма: {payment['amount']} ₽.\nПосле подтверждения оплаты слоты появятся автоматически. Сроки подписок сохранятся.",
            build_payment_keyboard(confirmation_url=payment.get("confirmation_url"), payment_id=payment["id"], source="slots"))
    except httpx.RequestError:
        await show_slot_error(callback)


async def show_slot_error(callback):
    await edit_screen(callback, "⚠️ Не удалось создать оплату. Проверьте активную подписку и попробуйте снова.",
        build_keyboard(inline_keyboard=[[InlineKeyboardButton(text="← К лимиту", callback_data="device_slots")]]))
