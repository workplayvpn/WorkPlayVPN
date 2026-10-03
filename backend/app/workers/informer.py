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
from app.services.help_access import key_for

logger = logging.getLogger("informer-worker")


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
            send_message(event.text + "\n\n🔑 Ключ помощи: " + key_for(user, token))
        except RuntimeError:
            event.next_attempt_at = datetime.now(UTC) + timedelta(seconds=min(3600, 10 * 2 ** min(event.attempts, 9)))
            logger.warning("Informer delivery retained for retry: payment_id=%s", event.payment_id)
        else:
            event.sent_at = datetime.now(UTC)
            logger.info("Informer delivered: payment_id=%s", event.payment_id)
        database.commit()
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
    while True:
        try:
            if process_once():
                continue
        except Exception:
            logger.error("Informer queue unavailable; retrying")
        time.sleep(10)


if __name__ == "__main__":
    main()
