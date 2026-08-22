import argparse
import logging
import time
from datetime import UTC, datetime

from sqlalchemy import select

from app.db.session import SessionLocal

# Эти импорты также гарантируют, что связанные таблицы
# зарегистрированы в SQLAlchemy metadata в отдельном worker-процессе.
from app.models.location import Location  # noqa: F401
from app.models.plan import Plan  # noqa: F401
from app.models.subscription import Subscription
from app.models.user import User  # noqa: F401
from app.models.vpn_device import VpnDevice  # noqa: F401
from app.models.vpn_node import VpnNode  # noqa: F401

from app.services.subscription_service import (
    subscription_service,
)


logging.basicConfig(
    level=logging.INFO,
    format=(
        "%(asctime)s "
        "%(levelname)s "
        "%(name)s "
        "%(message)s"
    ),
)

logger = logging.getLogger(
    "subscription-expiry-worker"
)


def get_expired_subscription_ids() -> list[int]:
    now = datetime.now(UTC)

    with SessionLocal() as database:
        return list(
            database.scalars(
                select(Subscription.id)
                .where(
                    Subscription.status == "active",
                    Subscription.expires_at.is_not(None),
                    Subscription.expires_at <= now,
                )
                .order_by(
                    Subscription.expires_at.asc()
                )
            ).all()
        )


def process_subscription(
    subscription_id: int,
) -> bool:
    with SessionLocal() as database:
        subscription = database.get(
            Subscription,
            subscription_id,
        )

        if subscription is None:
            return False

        if subscription.status != "active":
            return False

        subscription_service.expire_if_needed(
            database=database,
            subscription=subscription,
        )

        logger.info(
            "Expired subscription id=%s user_id=%s",
            subscription.id,
            subscription.user_id,
        )

        return True


def run_once() -> None:
    subscription_ids = (
        get_expired_subscription_ids()
    )

    if not subscription_ids:
        logger.info(
            "No expired subscriptions found"
        )
        return

    logger.info(
        "Found %s expired subscription(s)",
        len(subscription_ids),
    )

    success_count = 0

    for subscription_id in subscription_ids:
        try:
            if process_subscription(
                subscription_id
            ):
                success_count += 1
        except Exception:
            logger.exception(
                "Failed to expire subscription id=%s",
                subscription_id,
            )

    logger.info(
        "Expiry pass complete: processed=%s failed=%s",
        success_count,
        len(subscription_ids) - success_count,
    )


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--once",
        action="store_true",
        help="Run one expiry pass and exit.",
    )

    parser.add_argument(
        "--interval",
        type=int,
        default=60,
        help="Seconds between expiry passes.",
    )

    args = parser.parse_args()

    if args.once:
        run_once()
        return

    logger.info(
        "Subscription expiry worker started; "
        "interval=%ss",
        args.interval,
    )

    while True:
        try:
            run_once()
        except Exception:
            logger.exception(
                "Unexpected worker error"
            )

        time.sleep(
            args.interval
        )


if __name__ == "__main__":
    main()