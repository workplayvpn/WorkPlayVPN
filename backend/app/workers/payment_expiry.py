import argparse
import logging
import time
from datetime import UTC, datetime

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.payment import Payment
from app.models.subscription import Subscription
from app.models.plan import Plan
from app.models.user import User
from app.services.payment_providers import (
    payment_provider_registry,
)


logger = logging.getLogger(__name__)


def expire_pending_payments() -> int:
    database = SessionLocal()

    try:
        payment_ids = list(
            database.scalars(
                select(Payment.id).where(
                    Payment.status == "pending",
                    Payment.expires_at.is_not(None),
                    Payment.expires_at <= datetime.now(UTC),
                )
            ).all()
        )
    finally:
        database.close()

    expired_count = 0

    for payment_id in payment_ids:
        database = SessionLocal()

        try:
            payment = database.scalar(
                select(Payment)
                .where(
                    Payment.id == payment_id,
                )
                .with_for_update()
            )

            if payment is None:
                continue

            if payment.status != "pending":
                continue

            if payment.expires_at is None:
                continue

            if payment.expires_at > datetime.now(UTC):
                continue

            subscription = database.get(
                Subscription,
                payment.subscription_id,
            )

            provider_service = (
                payment_provider_registry.get(
                    payment.provider
                )
            )

            if payment.provider_payment_id is not None:
                provider_service.cancel_payment(
                    provider_payment_id=(
                        payment.provider_payment_id
                    ),
                )

            payment.status = "expired"

            if (
                subscription is not None
                and subscription.status == "pending"
            ):
                subscription.status = "canceled"

            database.commit()
            expired_count += 1

        except Exception:
            database.rollback()

            logger.exception(
                "Failed to expire payment %s",
                payment_id,
            )

        finally:
            database.close()

    return expired_count


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--interval",
        type=int,
        default=60,
    )

    args = parser.parse_args()

    while True:
        expire_pending_payments()
        time.sleep(args.interval)


if __name__ == "__main__":
    main()