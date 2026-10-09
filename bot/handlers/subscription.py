from datetime import datetime
from base64 import b64decode
import httpx
from aiogram import F, Router
from aiogram.types import BufferedInputFile
from api.backend import backend_get, backend_post
from ui.helpers import edit_screen
from ui.main import main_menu
from ui.subscription import build_subscription_keyboard, build_subscription_secret_keyboard, build_tier_keyboard, tier_name

router = Router(name="subscription")

async def _load_subscription_data(telegram_id):
    response = await backend_get(f"/subscriptions/users/{telegram_id}/current")
    if response.status_code == 404:
        return None, [], None
    response.raise_for_status()
    subscription = response.json()
    devices_response = await backend_get(f"/devices/users/{telegram_id}")
    devices_response.raise_for_status()
    return subscription, devices_response.json(), None


def _tiers(subscription):
    if not subscription or subscription.get("status") != "active":
        return {}
    entries = subscription.get("active_subscriptions") or [subscription]
    return {item.get("access_tier") or ("mobile" if item.get("plan_code", "").startswith("mobile_") else "basic"): item for item in entries}


def _build_subscription_text(subscription, devices, tier=None):
    tiers = _tiers(subscription)
    if not tiers and subscription and subscription.get("status") == "pending":
        return "🔑 Мои подписки\n\nОжидается подтверждение оплаты. Доступ появится после подтверждения платежа."
    if not tiers:
        return "🔑 Мои подписки\n\nАктивных подписок пока нет. Выберите подписку в каталоге."
    lines=[f"🔑 {tier_name(tier)} · Work&PlayVPN" if tier else "🔑 Мои подписки", ""]
    for name, item in tiers.items():
        if tier and name != tier: continue
        expiry=datetime.fromisoformat(item["expires_at"].replace("Z", "+00:00"))
        lines.append(f"{tier_name(name)} — до {expiry:%d.%m.%Y}")
    lines += ["", f"Устройства: {len(devices)} из {subscription['total_device_limit']}", "Устройства и их лимит общие. Сроки Basic и Pro независимы."]
    for device in devices[:5]:
        lines.append(f"• {device['device_name']}" + (f"\n  ID: {device['public_id']}" if device.get('public_id') else ""))
    if len(devices)>5: lines.append("Полный список устройств — в Mini App.")
    return "\n".join(lines)


@router.callback_query(F.data == "subscription")
@router.callback_query(F.data.startswith("subscription_tier:"))
async def show_subscription(callback):
    await callback.answer()
    try:
        subscription, devices, _ = await _load_subscription_data(callback.from_user.id)
        tiers=_tiers(subscription)
        tier=callback.data.split(":",1)[1] if ":" in callback.data else None
        if tier and tier not in tiers:
            await edit_screen(callback, "Эта подписка сейчас неактивна.", build_subscription_keyboard(active=False))
            return
        keyboard=(build_subscription_keyboard(active=True, tier=tier) if tier else
                  build_tier_keyboard(tiers, "subscription_tier", back="main_menu") if tiers else build_subscription_keyboard(active=False))
        await edit_screen(callback, _build_subscription_text(subscription, devices, tier), keyboard)
    except (httpx.HTTPError, ValueError, KeyError):
        await edit_screen(callback, "⚠️ Не удалось загрузить подписки. Попробуйте позже.", main_menu)


async def _get_token(telegram_id):
    response=await backend_post("/subscription-tokens", {"telegram_id":telegram_id})
    return response.json() if response.status_code == 201 else None


async def _secret(callback, qr=False):
    await callback.answer()
    if not callback.message or callback.message.chat.type != "private":
        return
    try:
        subscription, devices, _ = await _load_subscription_data(callback.from_user.id)
        tiers=_tiers(subscription)
        parts = callback.data.split(":")
        tier = parts[1] if len(parts) > 1 else None
        if tier is None:
            await edit_screen(callback, "Выберите подписку для QR-кода:" if qr else "Выберите подписку для ключа:",
                              build_tier_keyboard(tiers, "subscription_qr" if qr else "subscription_key"))
            return
        if tier not in tiers:
            await edit_screen(callback, "Подписка неактивна. Откройте каталог.", build_subscription_keyboard(active=False))
            return
        result = await backend_get(f"/subscription-tokens/happ/{tier}?telegram_id={callback.from_user.id}")
        result.raise_for_status()
        data = result.json()
        url = data['url']
        if not url.startswith("happ://crypt5/"):
            raise ValueError("Invalid Happ import key")
        keyboard=build_subscription_secret_keyboard(copy_value=url, tier=tier)
        if qr:
            await edit_screen(callback, f"📷 QR-код {tier_name(tier)}\n\nОтсканируйте в Happ на доверенном устройстве. Не передавайте другим людям.", keyboard,
                              photo=BufferedInputFile(b64decode(data['qr_png_base64'], validate=True), filename=f"subscription-{tier}.png"))
        else:
            await edit_screen(callback, f"🔑 Ключ Happ · {tier_name(tier)}\n\nОдин ключ для всех ваших устройств в этой подписке. Нажмите «Скопировать ключ».", keyboard)
    except (httpx.HTTPError, ValueError, KeyError):
        await edit_screen(callback, "⚠️ Не удалось получить ссылку. Попробуйте позже.", build_subscription_secret_keyboard())

@router.callback_query(F.data == "subscription_key")
@router.callback_query(F.data.startswith("subscription_key:"))
async def show_subscription_key(callback):
    await _secret(callback)

@router.callback_query(F.data == "subscription_qr")
@router.callback_query(F.data.startswith("subscription_qr:"))
async def show_subscription_qr(callback):
    await _secret(callback, qr=True)
