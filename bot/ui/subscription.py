from aiogram.types import InlineKeyboardButton, CopyTextButton, WebAppInfo
from config import mini_app_url
from ui.common import build_keyboard


def tier_name(tier):
    return "Pro" if tier == "mobile" else "Basic"


def key_copy_url(tier):
    return mini_app_url + ('&' if '?' in mini_app_url else '?') + f'view=subscriptions&key_action=copy&key_tier={tier}'


def build_tier_keyboard(tiers, action, *, back="subscription"):
    return build_keyboard(inline_keyboard=[
        [InlineKeyboardButton(text="📲 Pro" if t == "mobile" else "Basic",
            callback_data=f"{action}:{t}", style="primary" if t == "mobile" else None)]
        for t in ("mobile", "basic") if t in tiers
    ] + [[InlineKeyboardButton(text="← Назад", callback_data=back)]])


def build_subscription_keyboard(*, active, connect_url=None, mobile_connect_url=None, tier=None):
    if tier:
        rows = [[InlineKeyboardButton(text="📋 Скопировать ключ", web_app=WebAppInfo(url=key_copy_url(tier)), style="primary")],
                [InlineKeyboardButton(text="📷 Показать QR-код", callback_data=f"subscription_qr:{tier}", style="primary")],
                [InlineKeyboardButton(text="📖 Подключение и устройства", web_app=WebAppInfo(url=mini_app_url+('&' if '?' in mini_app_url else '?')+'view=devices'))],
                [InlineKeyboardButton(text="⏳ Продлить подписку", callback_data=f"plans_tier:{tier}:renew", style="primary")],
                [InlineKeyboardButton(text="➕ Добавить лимит устройств", callback_data=f"device_slots:{tier}", style="primary")],
                [InlineKeyboardButton(text="🌍 Сменить регион", callback_data=f"change_region:{tier}")],
                [InlineKeyboardButton(text="🛟 Сообщить о проблеме", url="https://t.me/workplayvpnteam")],
                [InlineKeyboardButton(text="← К подпискам", callback_data="subscription")]]
    else:
        rows = [[InlineKeyboardButton(text="💎 Выбрать подписку", callback_data="plans")],
                [InlineKeyboardButton(text="🚀 Открыть Work&PlayVPN", web_app=WebAppInfo(url=mini_app_url))],
                [InlineKeyboardButton(text="← На главную", callback_data="main_menu")]]
    return build_keyboard(inline_keyboard=rows)


def build_subscription_secret_keyboard(copy_value=None, mobile_copy_value=None, *, tier=None):
    rows=[]
    for label, value in ((tier_name(tier or "basic"), copy_value), ("Pro", mobile_copy_value)):
        if value and len(value) <= 256 and not any(row[0].copy_text and row[0].copy_text.text == value for row in rows):
            rows.append([InlineKeyboardButton(text=f"📋 Скопировать {label}", copy_text=CopyTextButton(text=value))])
        elif value:
            rows.append([InlineKeyboardButton(text="📋 Скопировать ключ", web_app=WebAppInfo(
                url=key_copy_url(tier or 'basic')))])
    rows.append([InlineKeyboardButton(text="← К подписке", callback_data=f"subscription_tier:{tier}" if tier else "subscription")])
    return build_keyboard(inline_keyboard=rows)
