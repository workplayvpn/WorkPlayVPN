import httpx
from aiogram import F, Router
from aiogram.types import InlineKeyboardButton
from api.backend import backend_get, backend_patch
from ui.helpers import edit_screen
from ui.common import build_keyboard
from ui.main import main_menu
from ui.navigation import subscription_tier, scoped_action, subscription_back

router = Router(name='locations')
FLAGS={'NL':'🇳🇱','DE':'🇩🇪','RU':'🇷🇺','FI':'🇫🇮'}

@router.callback_query(F.data.in_({'locations','change_region'}) | F.data.startswith('region_device:') | F.data.startswith('change_region:'))
async def show_region_devices(callback):
    await callback.answer()
    tier = subscription_tier(callback.data)
    try:
        response=await backend_get('/catalog/locations')
        response.raise_for_status()
        rows=[]
        for location in response.json():
            code=location['code']
            if code.upper() not in FLAGS: continue
            available=location.get('available',False)
            rows.append([InlineKeyboardButton(
                text=f"{FLAGS[code.upper()]} {location['name']}"+('' if available else ' · недоступно'),
                callback_data=scoped_action(f"account_region:{code}", tier) if available else 'region_unavailable',
                style='primary' if available else None)])
        rows.append([InlineKeyboardButton(text='← К подписке' if tier else '← К подпискам',callback_data=subscription_back(tier))])
        await edit_screen(callback,'🌍 Регион подписки\n\nНовый регион применяется ко всем устройствам Basic и Mobile. После смены обновите подписку в Happ.',build_keyboard(inline_keyboard=rows))
    except (httpx.HTTPError,ValueError,KeyError):
        await edit_screen(callback,'⚠️ Не удалось загрузить регионы.',region_error_keyboard(tier))

@router.callback_query(F.data=='region_unavailable')
async def unavailable_region(callback):
    await callback.answer('Этот регион временно недоступен.',show_alert=True)

@router.callback_query(F.data.startswith('account_region:') | F.data.startswith('region_location:'))
async def change_device_region(callback):
    await callback.answer('Меняем регион…')
    tier = subscription_tier(callback.data)
    parts = callback.data.split(':')
    code = parts[1] if parts[0] == 'account_region' else parts[-1]
    try:
        response=await backend_patch(f'/users/{callback.from_user.id}/region',{'location_code':code})
        response.raise_for_status()
        await edit_screen(callback,f"✅ Регион изменён: {response.json()['name']}\n\nИзменение применено ко всем устройствам. Обновите подписку в Happ.",build_keyboard(inline_keyboard=[
            [InlineKeyboardButton(text='🌍 Сменить регион',callback_data=scoped_action('change_region', tier))],
            [InlineKeyboardButton(text='← К подписке' if tier else '← К подпискам',callback_data=subscription_back(tier))]]))
    except (httpx.HTTPError,ValueError,KeyError):
        await edit_screen(callback,'⚠️ Не удалось сменить регион. Проверьте доступность региона и попробуйте позже.',region_error_keyboard(tier))


def region_error_keyboard(tier):
    if not tier:
        return main_menu
    return build_keyboard(inline_keyboard=[
        [InlineKeyboardButton(text='Повторить', callback_data=scoped_action('change_region', tier))],
        [InlineKeyboardButton(text='← К подписке', callback_data=subscription_back(tier))]])
