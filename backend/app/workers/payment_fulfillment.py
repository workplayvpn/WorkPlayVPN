import argparse
import logging
import time
from datetime import UTC

import httpx

from app.core.config import settings
from app.db.session import SessionLocal
from app.services.payment_fulfillment_service import (
    payment_fulfillment_service,
)


logger = logging.getLogger(
    "payment-fulfillment-worker"
)


def send_telegram_message(
    *,
    telegram_id: int,
    text: str,
) -> None:
    token = settings.telegram_bot_token

    if not token:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN is not configured"
        )

    url = (
        "https://api.telegram.org/"
        f"bot{token}/sendMessage"
    )

    try:
        response = httpx.post(
            url,
            json={
                "chat_id": telegram_id,
                "text": text,
                "disable_web_page_preview": True,
            },
            timeout=15.0,
        )
    except httpx.HTTPError as exc:
        raise RuntimeError(
            "Telegram request failed"
        ) from exc

    if response.status_code != 200:
        raise RuntimeError(
            "Telegram returned non-200 response"
        )

    try:
        payload = response.json()
    except ValueError as exc:
        raise RuntimeError(
            "Invalid Telegram response"
        ) from exc

    if payload.get("ok") is not True:
        raise RuntimeError(
            "Telegram sendMessage failed"
        )


def process_once() -> bool:
    database = SessionLocal()

    try:
        recovered = (
            payment_fulfillment_service
            .recover_stale_processing(
                database=database,
            )
        )

        if recovered:
            logger.warning(
                "Recovered stale fulfillments: count=%s",
                recovered,
            )

        fulfillment = (
            payment_fulfillment_service.claim_next(
                database=database,
            )
        )

        if fulfillment is None:
            return False

        logger.info(
            "Fulfillment claimed: "
            "fulfillment_id=%s "
            "payment_id=%s "
            "attempt=%s",
            fulfillment.id,
            fulfillment.payment_id,
            fulfillment.attempts,
        )

        try:
            (
                user,
                payment,
                subscription,
                device,
                vless_url,
            ) = payment_fulfillment_service.build_access(
                database=database,
                fulfillment=fulfillment,
            )

            expires_text = "не ограничен"

            if subscription.expires_at is not None:
                expires_at = subscription.expires_at

                if expires_at.tzinfo is None:
                    expires_at = expires_at.replace(
                        tzinfo=UTC
                    )

                expires_text = (
                    expires_at.astimezone(UTC)
                    .strftime("%d.%m.%Y")
                )

            text = (
                "✅ Оплата получена!\n\n"
                "🛡 Подписка Work&PlayVPN "
                "активирована.\n"
                f"📅 Действует до: {expires_text}\n\n"
                f"📱 Устройство: "
                f"{device.device_name}\n\n"
                "🔑 Ваш VPN-ключ:\n"
                f"{vless_url}\n\n"
                "Скопируйте ссылку и импортируйте "
                "её в совместимое VPN-приложение."
            )

            send_telegram_message(
                telegram_id=user.telegram_id,
                text=text,
            )

            payment_fulfillment_service.mark_delivered(
                database=database,
                fulfillment=fulfillment,
            )

            logger.info(
                "Fulfillment delivered: "
                "fulfillment_id=%s "
                "payment_id=%s "
                "telegram_id=%s "
                "device_id=%s",
                fulfillment.id,
                payment.id,
                user.telegram_id,
                device.id,
            )

            return True

        except Exception as exc:
            database.rollback()

            payment_fulfillment_service.mark_failed(
                database=database,
                fulfillment=fulfillment,
                error=str(exc),
            )

            logger.exception(
                "Fulfillment attempt failed: "
                "fulfillment_id=%s "
                "attempt=%s",
                fulfillment.id,
                fulfillment.attempts,
            )

            return True

    finally:
        database.close()


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--interval",
        type=int,
        default=10,
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format=(
            "%(asctime)s %(levelname)s "
            "%(name)s %(message)s"
        ),
    )

    # Не допускаем попадания Telegram Bot Token
    # в INFO-логи HTTP-клиента.
    logging.getLogger("httpx").setLevel(
        logging.WARNING
    )
    logging.getLogger("httpcore").setLevel(
        logging.WARNING
    )

    logger.info(
        "Payment fulfillment worker started; "
        "interval=%ss",
        args.interval,
    )

    while True:
        processed = process_once()

        if not processed:
            time.sleep(args.interval)


if __name__ == "__main__":
    main()