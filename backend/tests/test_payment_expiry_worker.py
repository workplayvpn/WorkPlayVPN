from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.payment import Payment
from app.models.plan import Plan
from app.models.subscription import Subscription
from app.models.user import User
from app.workers.payment_expiry import expire_pending_payments


@pytest.fixture
def database():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.rollback()
        db.close()


def test_expired_pending_payment_is_closed(
    database,
) -> None:
    user = User(
        telegram_id=999100001,
        username="payment_expiry_test",
        first_name="PaymentExpiry",
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
        idempotency_key="payment-expiry-001",
        status="pending",
        amount=Decimal("199.00"),
        currency="RUB",
        confirmation_url=None,
        expires_at=(
            datetime.now(UTC)
            - timedelta(minutes=1)
        ),
    )

    database.add(payment)
    database.commit()

    payment_id = payment.id
    subscription_id = subscription.id

    expired_count = expire_pending_payments()

    assert expired_count >= 1

    database.expire_all()

    updated_payment = database.get(
        Payment,
        payment_id,
    )

    updated_subscription = database.get(
        Subscription,
        subscription_id,
    )

    assert updated_payment is not None
    assert updated_subscription is not None

    assert updated_payment.status == "expired"
    assert updated_subscription.status == "canceled"


def test_unexpired_pending_payment_is_not_closed(
    database,
) -> None:
    user = User(
        telegram_id=999100002,
        username="payment_expiry_test_2",
        first_name="PaymentExpiry2",
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
        idempotency_key="payment-expiry-002",
        status="pending",
        amount=Decimal("199.00"),
        currency="RUB",
        confirmation_url=None,
        expires_at=(
            datetime.now(UTC)
            + timedelta(hours=23)
        ),
    )

    database.add(payment)
    database.commit()

    payment_id = payment.id
    subscription_id = subscription.id

    expire_pending_payments()

    database.expire_all()

    updated_payment = database.get(
        Payment,
        payment_id,
    )

    updated_subscription = database.get(
        Subscription,
        subscription_id,
    )

    assert updated_payment is not None
    assert updated_subscription is not None

    assert updated_payment.status == "pending"
    assert updated_subscription.status == "pending"