"""Paid, single-use gifts; the database arbitrates ownership and redemption."""
import base64
import hashlib
import hmac
import re
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import select

from app.core.config import settings
from app.models.gift import GiftCertificate, GiftAttemptWindow
from app.models.informer_notification import InformerNotification
from app.models.payment import Payment
from app.models.plan import Plan
from app.models.subscription import Subscription
from app.models.user import User
from app.services.mobile_rollout import mobile_pilot_allowed
from app.services.subscription_service import subscription_service


def utc(value):
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


def raw_code(gift):
    message = f"workplay-gift-v1:{gift.id}:{gift.buyer_id}".encode()
    digest = hmac.new(settings.subscription_token_secret.encode(), message, hashlib.sha256).digest()
    return base64.b32encode(digest[:15]).decode()


def code_hash(code):
    return hmac.new(settings.subscription_token_secret.encode(), b"gift-lookup-v1:" + code.encode(), hashlib.sha256).hexdigest()


def normalize_code(code):
    value = re.sub(r"[\s-]", "", code).upper()
    if not re.fullmatch(r"[A-Z2-7]{24}", value):
        raise HTTPException(400, "Подарочный код недействителен или уже использован.")
    return value


def display_code(gift):
    code = raw_code(gift)
    return "-".join(code[i:i+4] for i in range(0, len(code), 4))


def prepare_gift_order(db, payment, plan):
    db.add(GiftCertificate(id=str(uuid.uuid4()), payment_id=payment.id,
        buyer_id=payment.user_id, plan_id=plan.id, access_tier=plan.access_tier,
        duration_days=plan.duration_days, device_limit=plan.device_limit, state="pending"))


def issue_paid_gift(db, payment):
    if payment.status != "succeeded" or payment.purpose != "gift":
        raise RuntimeError("Gift payment is not confirmed")
    gift = db.scalar(select(GiftCertificate).where(GiftCertificate.payment_id == payment.id).with_for_update())
    if gift is None:
        raise RuntimeError("Gift order missing")
    if gift.state != "pending":
        return gift
    # Freeze the purchased duration and device limit even if catalogue changes.
    plan = Plan(code="gift_" + gift.id.replace("-", ""), name=f"Подарок {gift.access_tier.title()} — {gift.duration_days} дней",
        duration_days=gift.duration_days, device_limit=gift.device_limit,
        price_amount=0, currency=payment.currency, access_tier=gift.access_tier, is_active=False)
    db.add(plan)
    db.flush()
    gift.plan_id = plan.id
    gift.state = "ready"
    gift.issued_at = datetime.now(UTC)
    gift.code_hash = code_hash(raw_code(gift))
    return gift


def consume_attempt(db, user_id):
    owner = db.scalar(select(User).where(User.id == user_id, User.is_active.is_(True)).with_for_update())
    if owner is None:
        raise HTTPException(404, "User not found")
    now = datetime.now(UTC)
    window = db.get(GiftAttemptWindow, user_id)
    if window is None:
        window = GiftAttemptWindow(user_id=user_id, started_at=now, attempts=0)
        db.add(window)
    if utc(window.started_at) + timedelta(minutes=15) <= now:
        window.started_at, window.attempts = now, 0
    if window.attempts >= 10:
        raise HTTPException(429, "Слишком много попыток. Попробуйте через 15 минут.")
    window.attempts += 1
    # Invalid attempts survive request rollback and server restarts.
    db.commit()


def validate_gift(db, gift, recipient_id):
    if gift is None:
        raise HTTPException(400, "Подарочный код недействителен или уже использован.")
    payment = db.get(Payment, gift.payment_id)
    if payment is None or payment.status != "succeeded" or payment.purpose != "gift":
        raise HTTPException(400, "Подарочный код недействителен или уже использован.")
    if gift.buyer_id == recipient_id:
        raise HTTPException(409, "Нельзя активировать собственный подарок. Передайте его другому человеку.")
    if gift.state == "redeemed":
        if gift.recipient_id == recipient_id:
            return gift
        raise HTTPException(400, "Подарочный код недействителен или уже использован.")
    if gift.state != "ready":
        raise HTTPException(400, "Подарочный код недействителен или уже использован.")
    if gift.access_tier == "mobile" and not mobile_pilot_allowed(recipient_id):
        raise HTTPException(409, "Pro пока недоступен этому аккаунту. Подарок не использован.")
    if payment.provider == "test" and settings.payment_mode != "test":
        raise HTTPException(409, "Тестовый подарок нельзя активировать в рабочем режиме.")
    # Test mode is snapshotted on the payment, not inferred from a later switch.
    if payment.is_gift_test and settings.payment_mode != "test":
        raise HTTPException(409, "Тестовый подарок нельзя активировать в рабочем режиме.")
    return gift


def preview_gift(db, user_id, code):
    consume_attempt(db, user_id)
    digest = code_hash(normalize_code(code))
    gift = db.scalar(select(GiftCertificate).where(GiftCertificate.code_hash == digest))
    validate_gift(db, gift, user_id)
    return dict(access_tier=gift.access_tier, duration_days=gift.duration_days, already_activated=gift.state == "redeemed")


def redeem_gift(db, user_id, code):
    consume_attempt(db, user_id)
    digest = code_hash(normalize_code(code))
    # Expiry can commit while revoking node access: finish it before locking
    # the gift. No such commit is allowed during the redemption transaction.
    subscription_service.expire_stale_subscriptions(db, user_id)
    owner = db.scalar(select(User).where(User.id == user_id, User.is_active.is_(True)).with_for_update())
    if owner is None:
        raise HTTPException(404, "User not found")
    gift = db.scalar(select(GiftCertificate).where(GiftCertificate.code_hash == digest).with_for_update().execution_options(populate_existing=True))
    validate_gift(db, gift, user_id)
    if gift.state == "redeemed":
        return dict(access_tier=gift.access_tier, duration_days=gift.duration_days, already_activated=True)
    grant = Subscription(user_id=user_id, plan_id=gift.plan_id, status="pending")
    db.add(grant)
    db.flush()
    gift.state = "redeemed"
    gift.recipient_id = user_id
    gift.redeemed_subscription_id = grant.id
    gift.redeemed_at = datetime.now(UTC)
    buyer = db.get(User, gift.buyer_id)
    event = InformerNotification(id=str(uuid.uuid4()), payment_id=None,
        event_key="gift:" + gift.id + ":activated", user_id=user_id,
        text="\n".join(["🎁 Подарок активирован", "🧪 Тестовый подарок" if db.get(Payment, gift.payment_id).is_gift_test else "💳 Оплаченный подарок", f"Telegram ID: {owner.telegram_id}",
            f"Username: @{owner.username}" if owner.username else "Username: не указан",
            f"Покупатель Telegram ID: {buyer.telegram_id}", f"Подарок: #{gift.id}",
            f"Подписка: {gift.access_tier.title()}", f"Срок: {gift.duration_days} дней"]))
    db.add(event)
    # This commit also persists the claim and notification. On provisioning
    # failure the existing activation service rolls everything back.
    subscription_service.activate_subscription(db, grant, skip_expiry=True)
    return dict(access_tier=gift.access_tier, duration_days=gift.duration_days, already_activated=False)
