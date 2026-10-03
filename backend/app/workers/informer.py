"""Deliver private purchase notifications through the separate informer bot."""
import argparse
import logging
import time
from datetime import UTC, datetime, timedelta
import httpx
from sqlalchemy import select
from app.core.config import settings
from app.db.session import SessionLocal
from app.models.informer_notification import InformerNotification
from app.models.user import User
from app.models.subscription_token import SubscriptionToken
from app.models.payment import Payment  # noqa: F401 — resolve queue FK in standalone worker
from app.models.location import Location  # noqa: F401 — resolve user FK when creating a token
from app.services.help_access import key_for
from app.models.abuse_alert import AbuseAlert
from app.services.abuse_observation import scan

logger = logging.getLogger("informer-worker")
_accepted_events = set()
_accepted_alerts = set()


def scan_abuse_once():
    if not settings.antifraud_observe_enabled or not settings.informer_bot_token:
        return 0
    with SessionLocal() as database:
        count = scan(database)
        database.commit()
        return count


def process_alert_once():
    if (not settings.antifraud_observe_enabled or not settings.informer_bot_token
            or settings.informer_owner_telegram_id <= 0):
        return False
    with SessionLocal() as database:
        event = database.scalar(select(AbuseAlert).where(
            AbuseAlert.sent_at.is_(None),
            AbuseAlert.next_attempt_at <= datetime.now(UTC)).order_by(
            AbuseAlert.created_at, AbuseAlert.id).with_for_update(skip_locked=True).limit(1))
        if event is None:
            return False
        event.attempts += 1
        try:
            if event.id not in _accepted_alerts:
                send_message(event.text)
                _accepted_alerts.add(event.id)
        except RuntimeError:
            event.next_attempt_at = datetime.now(UTC) + timedelta(
                seconds=min(3600, 10 * 2 ** min(event.attempts, 9)))
            logger.warning("Observation alert retained for retry: rule=%s", event.rule)
        else:
            event.sent_at = datetime.now(UTC)
        event_id, delivered = event.id, event.sent_at is not None
        database.commit()
        _accepted_alerts.discard(event_id)
        if delivered:
            logger.info("Observation alert delivered: id=%s", event_id)
        return True


def render_message(event, user, token):
    # Repair old queued snapshots too; numeric tg:// links are unreliable in plain text.
    username = (user.username or "").lstrip("@")
    profile = "https://t.me/" + username if username else "публичный @username не указан"
    lines = ["Профиль: " + profile if line.startswith("Профиль: ") else line
             for line in event.text.splitlines()]
    return "\n".join(lines) + "\n\n🔑 Ключ помощи: " + key_for(user, token)


def send_message(text):
    if not settings.informer_bot_token or settings.informer_owner_telegram_id <= 0:
        raise RuntimeError("Informer not configured")
    # Plain text: user-supplied names cannot inject HTML or Markdown links.
    try:
        with httpx.Client(proxy=settings.telegram_proxy_url or None, timeout=15) as client:
            response = client.post(f"https://api.telegram.org/bot{settings.informer_bot_token}/sendMessage",
                json={"chat_id": settings.informer_owner_telegram_id, "text": text,
                      "disable_web_page_preview": True})
        if response.status_code != 200 or response.json().get("ok") is not True:
            raise RuntimeError("Informer delivery failed")
    except (httpx.HTTPError, ValueError):
        # Exception URLs may include the bot token. Do not log response bodies or exceptions.
        raise RuntimeError("Informer delivery failed") from None


def process_once():
    if not settings.informer_bot_token or settings.informer_owner_telegram_id <= 0:
        return False
    with SessionLocal() as database:
        # Hold the row lock during delivery. Concurrent workers skip claimed rows.
        event = database.scalar(select(InformerNotification).where(
            InformerNotification.sent_at.is_(None),
            InformerNotification.next_attempt_at <= datetime.now(UTC)).order_by(
            InformerNotification.created_at, InformerNotification.id).with_for_update(skip_locked=True).limit(1))
        if event is None:
            return False
        user = database.scalar(select(User).where(User.id == event.user_id).with_for_update())
        token = database.scalar(select(SubscriptionToken).where(SubscriptionToken.user_id == event.user_id))
        if token is None:
            token = SubscriptionToken(user_id=user.id, version=1)
            database.add(token)
            database.flush()
        event.attempts += 1
        try:
            if event.id not in _accepted_events:
                send_message(render_message(event, user, token))
                # A transient commit failure must not resend in the same process.
                _accepted_events.add(event.id)
        except RuntimeError:
            event.next_attempt_at = datetime.now(UTC) + timedelta(seconds=min(3600, 10 * 2 ** min(event.attempts, 9)))
            logger.warning("Informer delivery retained for retry: payment_id=%s", event.payment_id)
        else:
            event.sent_at = datetime.now(UTC)
        event_id, payment_id, delivered = event.id, event.payment_id, event.sent_at is not None
        database.commit()
        _accepted_events.discard(event_id)
        if delivered:
            logger.info("Informer delivered: payment_id=%s", payment_id)
        return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    if args.test:
        send_message("✅ Work&PlayVPN Informer подключён. Уведомления о покупках будут приходить сюда.")
        print("Informer test delivered")
        return
    next_scan = 0.0
    while True:
        if time.monotonic() >= next_scan:
            next_scan = time.monotonic() + 60
            try:
                scan_abuse_once()
            except Exception as exc:
                logger.error("Observation scan unavailable: %s", type(exc).__name__)
        worked = False
        try:
            worked = process_once()
        except Exception as exc:
            logger.error("Informer queue unavailable: %s; retrying", type(exc).__name__)
        try:
            worked = process_alert_once() or worked
        except Exception as exc:
            logger.error("Observation queue unavailable: %s", type(exc).__name__)
        if not worked:
            time.sleep(10)


if __name__ == "__main__":
    main()
