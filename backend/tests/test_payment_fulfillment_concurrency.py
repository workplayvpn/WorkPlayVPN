from decimal import Decimal

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.payment import Payment
from app.models.payment_fulfillment import PaymentFulfillment
from app.models.plan import Plan
from app.models.subscription import Subscription
from app.models.user import User
from app.services.payment_fulfillment_service import (
    payment_fulfillment_service,
)
from app.services.payment_service import payment_service


def create_fulfillment() -> int:
    database = SessionLocal()

    try:
        user = User(
            telegram_id=994000001,
            username="fulfillment_concurrency",
            first_name="Concurrency",
            is_active=True,
        )

        database.add(user)
        database.flush()

        plan = database.scalar(
            select(Plan).where(
                Plan.code == "standard_1m",
            )
        )

        assert plan is not None

        subscription = Subscription(
            user_id=user.id,
            plan_id=plan.id,
            status="pending",
        )

        database.add(subscription)
        database.flush()

        payment = Payment(
            user_id=user.id,
            subscription_id=subscription.id,
            provider="test",
            provider_payment_id=None,
            idempotency_key="fulfillment-concurrency-001",
            status="pending",
            amount=Decimal("199.00"),
            currency="RUB",
            confirmation_url=None,
        )

        database.add(payment)
        database.commit()

        payment_service.mark_succeeded(
            database=database,
            payment_id=payment.id,
            provider_payment_id="provider-concurrency-001",
        )

        fulfillment = database.scalar(
            select(PaymentFulfillment).where(
                PaymentFulfillment.payment_id == payment.id,
            )
        )

        assert fulfillment is not None

        return fulfillment.id

    finally:
        database.close()


def test_second_worker_cannot_claim_processing_fulfillment() -> None:
    fulfillment_id = create_fulfillment()

    worker_1 = SessionLocal()
    worker_2 = SessionLocal()

    try:
        first = payment_fulfillment_service.claim_next(
            database=worker_1,
        )

        assert first is not None
        assert first.id == fulfillment_id
        assert first.status == "processing"

        second = payment_fulfillment_service.claim_next(
            database=worker_2,
        )

        assert second is None

        worker_1.expire_all()
        worker_2.expire_all()

        stored = worker_2.get(
            PaymentFulfillment,
            fulfillment_id,
        )

        assert stored is not None
        assert stored.status == "processing"
        assert stored.attempts == 1

    finally:
        worker_1.rollback()
        worker_2.rollback()
        worker_1.close()
        worker_2.close()