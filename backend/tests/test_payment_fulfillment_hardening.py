from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
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


@pytest.fixture
def database():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.rollback()
        db.close()


def create_succeeded_payment(
    database,
    *,
    telegram_id: int,
    idempotency_key: str,
) -> tuple[User, Payment, PaymentFulfillment]:
    user = User(
        telegram_id=telegram_id,
        username=f"user_{telegram_id}",
        first_name="FulfillmentTest",
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
        idempotency_key=idempotency_key,
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
        provider_payment_id=f"provider-{payment.id}",
    )

    fulfillment = database.scalar(
        select(PaymentFulfillment).where(
            PaymentFulfillment.payment_id == payment.id,
        )
    )

    assert fulfillment is not None

    return user, payment, fulfillment


def test_claim_moves_pending_to_processing(
    database,
) -> None:
    _, payment, fulfillment = create_succeeded_payment(
        database,
        telegram_id=993000001,
        idempotency_key="fulfillment-claim-001",
    )

    assert fulfillment.status == "pending"
    assert fulfillment.attempts == 0

    claimed = payment_fulfillment_service.claim_next(
        database=database,
    )

    assert claimed is not None
    assert claimed.payment_id == payment.id
    assert claimed.status == "processing"
    assert claimed.attempts == 1
    assert claimed.processing_started_at is not None
    assert claimed.next_attempt_at is None


def test_failed_attempt_schedules_retry(
    database,
) -> None:
    _, payment, _ = create_succeeded_payment(
        database,
        telegram_id=993000002,
        idempotency_key="fulfillment-retry-001",
    )

    claimed = payment_fulfillment_service.claim_next(
        database=database,
    )

    assert claimed is not None
    assert claimed.payment_id == payment.id
    assert claimed.attempts == 1

    before = datetime.now(UTC)

    payment_fulfillment_service.mark_failed(
        database=database,
        fulfillment=claimed,
        error="temporary failure",
    )

    database.refresh(claimed)

    after = datetime.now(UTC)

    assert claimed.status == "pending"
    assert claimed.processing_started_at is None
    assert claimed.last_error == "temporary failure"
    assert claimed.next_attempt_at is not None

    expected_min = before + timedelta(seconds=10)
    expected_max = after + timedelta(seconds=10)

    assert expected_min <= claimed.next_attempt_at <= expected_max

    # До наступления next_attempt_at повторно
    # забираться не должна.
    another = payment_fulfillment_service.claim_next(
        database=database,
    )

    assert another is None


def test_fulfillment_becomes_failed_after_max_attempts(
    database,
) -> None:
    _, _, fulfillment = create_succeeded_payment(
        database,
        telegram_id=993000003,
        idempotency_key="fulfillment-max-attempts-001",
    )

    fulfillment.status = "processing"
    fulfillment.attempts = (
        payment_fulfillment_service.max_attempts
    )
    fulfillment.processing_started_at = datetime.now(UTC)

    database.commit()
    database.refresh(fulfillment)

    payment_fulfillment_service.mark_failed(
        database=database,
        fulfillment=fulfillment,
        error="permanent failure",
    )

    database.refresh(fulfillment)

    assert fulfillment.status == "failed"
    assert (
        fulfillment.attempts
        == payment_fulfillment_service.max_attempts
    )
    assert fulfillment.next_attempt_at is None
    assert fulfillment.processing_started_at is None
    assert fulfillment.last_error == "permanent failure"


def test_stale_processing_is_recovered(
    database,
) -> None:
    _, _, fulfillment = create_succeeded_payment(
        database,
        telegram_id=993000004,
        idempotency_key="fulfillment-stale-001",
    )

    stale_time = datetime.now(UTC) - timedelta(
        minutes=(
            payment_fulfillment_service
            .processing_lease_minutes
            + 1
        )
    )

    fulfillment.status = "processing"
    fulfillment.attempts = 1
    fulfillment.processing_started_at = stale_time
    fulfillment.next_attempt_at = None

    database.commit()

    recovered_count = (
        payment_fulfillment_service
        .recover_stale_processing(
            database=database,
        )
    )

    assert recovered_count == 1

    database.refresh(fulfillment)

    assert fulfillment.status == "pending"
    assert fulfillment.processing_started_at is None
    assert fulfillment.next_attempt_at is not None


def test_fresh_processing_is_not_recovered(
    database,
) -> None:
    _, _, fulfillment = create_succeeded_payment(
        database,
        telegram_id=993000005,
        idempotency_key="fulfillment-fresh-001",
    )

    fulfillment.status = "processing"
    fulfillment.attempts = 1
    fulfillment.processing_started_at = datetime.now(UTC)
    fulfillment.next_attempt_at = None

    database.commit()

    recovered_count = (
        payment_fulfillment_service
        .recover_stale_processing(
            database=database,
        )
    )

    assert recovered_count == 0

    database.refresh(fulfillment)

    assert fulfillment.status == "processing"
    assert fulfillment.processing_started_at is not None