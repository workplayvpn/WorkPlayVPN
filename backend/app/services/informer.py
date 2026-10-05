"""Queue snapshots in the purchase transaction; never store access keys."""
from datetime import UTC
from uuid import uuid4
from zoneinfo import ZoneInfo
from sqlalchemy import select
from app.models.informer_notification import InformerNotification
from app.models.user import User
from app.models.plan import Plan
from app.models.subscription import Subscription
from app.services.device_slots import slot_count
from app.services.entitlements import active_entitlements, shared_device_limit


def enqueue_purchase(database, payment, *, user=None, subscription=None, plan=None):
    if payment.status != "succeeded":
        return
    if database.scalar(select(InformerNotification.id).where(InformerNotification.payment_id == payment.id)):
        return
    user = user or database.get(User, payment.user_id)
    subscription = subscription or database.get(Subscription, payment.subscription_id)
    plan = plan or (database.get(Plan, subscription.plan_id) if subscription else None)
    if not user or not subscription or not plan:
        raise RuntimeError("Informer purchase metadata missing")
    slots = slot_count(plan)
    gift = getattr(payment, "purpose", "subscription") == "gift"
    title = "🎁 Куплен подарок" if gift else "📱 Куплены дополнительные устройства" if slots else "✅ Подписка оформлена / продлена"
    test = payment.provider == "test"
    from app.core.config import settings
    test = test or settings.payment_mode == "test" or (payment.provider == "robokassa" and settings.robokassa_is_test)
    lines = [title, "🧪 ТЕСТОВАЯ ОПЛАТА" if test else "💳 Подтверждённая оплата", "",
             f"Telegram ID: {user.telegram_id}",
             f"Username: @{user.username}" if user.username else "Username: не указан",
             f"Профиль: https://t.me/{user.username.lstrip('@')}" if user.username else "Профиль: публичный @username не указан",
             f"Платёж: #{payment.id}", f"Сумма: {payment.amount} {payment.currency}"]
    if gift:
        lines += [f"Подарок: {plan.access_tier.title()} — {plan.name}", f"Срок: {plan.duration_days} дней", "Код готов к передаче получателю. Срок активации не ограничен."]
    elif slots:
        limit = shared_device_limit(active_entitlements(database, user.id), user.extra_device_slots)
        lines += [f"Куплено устройств: +{slots}", f"Новый общий лимит: {limit}"]
    else:
        expiry = subscription.expires_at
        if expiry and expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=UTC)
        lines += [f"Подписка: Work&PlayVPN {plan.access_tier.title()} — {plan.name}",
                  f"Оплаченный срок: {plan.duration_days} дней",
                  f"Действует до: {expiry.astimezone(ZoneInfo('Europe/Moscow')).strftime('%d.%m.%Y %H:%M МСК') if expiry else 'без ограничения'}"]
    database.add(InformerNotification(id=str(uuid4()), payment_id=payment.id,
                                     user_id=user.id, text='\n'.join(lines)))
