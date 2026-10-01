import httpx
from aiogram import F, Router
from aiogram.types import InlineKeyboardButton
from api.backend import backend_get, backend_patch
from ui.helpers import edit_screen
from ui.common import build_keyboard
from ui.main import main_menu

router = Router(name='locations')
FLAGS={'NL':'🇳🇱','DE':'🇩🇪','RU':'🇷🇺','FI':'🇫🇮'}

@router.callback_query(F.data.in_({'locations','change_region'}) | F.data.startswith('region_device:'))
async def show_region_devices(callback):
    await callback.answer()
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
                callback_data=f"account_region:{code}" if available else 'region_unavailable',
                style='primary' if available else None)])
        rows.append([InlineKeyboardButton(text='← К подпискам',callback_data='subscription')])
        await edit_screen(callback,'🌍 Регион подписки\n\nНовый регион применяется ко всем устройствам Basic и Mobile. После смены обновите подписку в Happ.',build_keyboard(inline_keyboard=rows))
    except (httpx.HTTPError,ValueError,KeyError):
        await edit_screen(callback,'⚠️ Не удалось загрузить регионы.',main_menu)

@router.callback_query(F.data=='region_unavailable')
async def unavailable_region(callback):
    await callback.answer('Этот регион временно недоступен.',show_alert=True)

@router.callback_query(F.data.startswith('account_region:') | F.data.startswith('region_location:'))
async def change_device_region(callback):
    await callback.answer('Меняем регион…')
    code=callback.data.rsplit(':',1)[-1]
    try:
        response=await backend_patch(f'/users/{callback.from_user.id}/region',{'location_code':code})
        response.raise_for_status()
        await edit_screen(callback,f"✅ Регион изменён: {response.json()['name']}\n\nИзменение применено ко всем устройствам. Обновите подписку в Happ.",build_keyboard(inline_keyboard=[
            [InlineKeyboardButton(text='🌍 Сменить регион',callback_data='change_region')],
            [InlineKeyboardButton(text='← К подпискам',callback_data='subscription')]]))
    except (httpx.HTTPError,ValueError,KeyError):
        await edit_screen(callback,'⚠️ Не удалось сменить регион. Проверьте доступность региона и попробуйте позже.',main_menu)
