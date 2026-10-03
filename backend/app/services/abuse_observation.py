"""Detect activity bursts from saved events, without changing user entitlements."""
from datetime import UTC, datetime, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo
from sqlalchemy import select, func
from app.models.abuse_alert import AbuseAlert
from app.models.user import User
from app.models.payment import Payment
from app.models.device_activation import DeviceActivation
from app.models.support_ticket import SupportTicket
from app.models.subscription import Subscription
from app.models.plan import Plan

WINDOW = timedelta(minutes=10)
COOLDOWN = timedelta(hours=1)
# Count saved records, not HTTP attempts or actual connected VPN devices.
RULES = (
    ("payment_burst", Payment, 8, "Создано платежей"),
    ("activation_burst", DeviceActivation, 10, "Создано ссылок активации устройств"),
    ("support_burst", SupportTicket, 5, "Создано обращений в поддержку"),
)


def candidates(database, now):
    for rule, model, threshold, label in RULES:
        rows = database.execute(select(model.user_id, func.count(model.id)).where(
            model.created_at >= now - WINDOW, model.created_at <= now).group_by(
            model.user_id).having(func.count(model.id) >= threshold).order_by(model.user_id))
        for user_id, count in rows:
            yield rule, user_id, f"{label}: {count} за 10 минут (порог {threshold})"
    # Multiple issued trials, not rejected trial requests.
    rows = database.execute(select(Subscription.user_id, func.count(Subscription.id)).join(
        Plan, Subscription.plan_id == Plan.id).where(Plan.code == "trial_1d",
        Subscription.created_at <= now).group_by(Subscription.user_id).having(
        func.count(Subscription.id) > 1, func.max(Subscription.created_at) >= now - WINDOW).order_by(Subscription.user_id))
    for user_id, count in rows:
        yield "duplicate_trial", user_id, f"Выдано пробных подписок одному аккаунту: {count}"


def scan(database, now=None):
    now = now or datetime.now(UTC)
    queued = 0
    for rule, user_id, detail in candidates(database, now):
        # Serialize scanners for a user; re-check cooldown after obtaining the lock.
        user = database.scalar(select(User).where(User.id == user_id).with_for_update())
        if user is None:
            continue
        existing = database.scalar(select(AbuseAlert.id).where(
            AbuseAlert.user_id == user_id, AbuseAlert.rule == rule,
            AbuseAlert.created_at > now - COOLDOWN).limit(1))
        if existing:
            continue
        username = (user.username or "").lstrip("@")
        profile = f"https://t.me/{username}" if username else "публичный @username не указан"
        message = "\n".join([
            "🔎 Work&PlayVPN — сигнал для проверки",
            "Режим наблюдения. Пользователь автоматически не заблокирован.", "",
            f"Telegram ID: {user.telegram_id}",
            f"Username: @{username}" if username else "Username: не указан",
            f"Профиль: {profile}", "", detail,
            f"Правило: {rule}",
            f"Проверено: {now.astimezone(ZoneInfo('Europe/Moscow')).strftime('%d.%m.%Y %H:%M МСК')}",
            "Частая активность сама по себе не доказывает злоупотребление.",
        ])
        database.add(AbuseAlert(id=str(uuid4()), user_id=user_id, rule=rule,
            text=message, created_at=now, next_attempt_at=now))
        database.flush()
        queued += 1
    return queued
