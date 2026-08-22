from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.payment import Payment
from app.models.plan import Plan
from app.models.subscription import Subscription
from app.models.user import User
from app.services.payment_service import payment_service


@pytest.fixture
def database():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.rollback()
        db.close()


def test_payment_succeeds_and_extends_active_subscription_once(
    database,
) -> None:
    user = User(
        telegram_id=991000001,
        username="integration_user",
        first_name="Integration",
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

    initial_expires_at = (
        datetime.now(UTC)
        + timedelta(days=10)
    )

    active_subscription = Subscription(
        user_id=user.id,
        plan_id=plan.id,
        status="active",
        starts_at=datetime.now(UTC),
        expires_at=initial_expires_at,
    )

    purchase_subscription = Subscription(
        user_id=user.id,
        plan_id=plan.id,
        status="pending",
    )

    database.add_all(
        [
            active_subscription,
            purchase_subscription,
        ]
    )

    database.flush()

    payment = Payment(
        user_id=user.id,
        subscription_id=purchase_subscription.id,
        provider="cloudpayments",
        provider_payment_id=None,
        idempotency_key="integration-payment-001",
        status="pending",
        amount=Decimal("199.00"),
        currency="RUB",
        confirmation_url=None,
    )

    database.add(payment)
    database.commit()

    payment_id = payment.id
    purchase_subscription_id = purchase_subscription.id
    active_subscription_id = active_subscription.id

    first_result = payment_service.mark_succeeded(
        database=database,
        payment_id=payment_id,
        provider_payment_id="cp-integration-001",
    )

    assert first_result.status == "succeeded"
    assert (
        first_result.provider_payment_id
        == "cp-integration-001"
    )
    assert first_result.paid_at is not None

    database.expire_all()

    updated_purchase = database.get(
        Subscription,
        purchase_subscription_id,
    )

    updated_active = database.get(
        Subscription,
        active_subscription_id,
    )

    assert updated_purchase is not None
    assert updated_active is not None

    assert updated_purchase.status == "applied"

    expected_expires_at = (
        initial_expires_at
        + timedelta(days=plan.duration_days)
    )

    assert updated_active.expires_at == expected_expires_at

    expires_after_first_confirmation = (
        updated_active.expires_at
    )

    second_result = payment_service.mark_succeeded(
        database=database,
        payment_id=payment_id,
        provider_payment_id="cp-integration-001",
    )

    assert second_result.status == "succeeded"

    database.expire_all()

    updated_active_again = database.get(
        Subscription,
        active_subscription_id,
    )

    assert updated_active_again is not None
    assert (
        updated_active_again.expires_at
        == expires_after_first_confirmation
    )


def test_payment_activates_subscription_when_no_active_exists(
    database,
) -> None:
    user = User(
        telegram_id=991000002,
        username="integration_user_2",
        first_name="Integration2",
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

    purchase_subscription = Subscription(
        user_id=user.id,
        plan_id=plan.id,
        status="pending",
    )

    database.add(purchase_subscription)
    database.flush()

    payment = Payment(
        user_id=user.id,
        subscription_id=purchase_subscription.id,
        provider="cloudpayments",
        provider_payment_id=None,
        idempotency_key="integration-payment-002",
        status="pending",
        amount=Decimal("199.00"),
        currency="RUB",
        confirmation_url=None,
    )

    database.add(payment)
    database.commit()

    payment_id = payment.id
    subscription_id = purchase_subscription.id

    before_activation = datetime.now(UTC)

    result = payment_service.mark_succeeded(
        database=database,
        payment_id=payment_id,
        provider_payment_id="cp-integration-002",
    )

    after_activation = datetime.now(UTC)

    assert result.status == "succeeded"

    database.expire_all()

    activated_subscription = database.get(
        Subscription,
        subscription_id,
    )

    assert activated_subscription is not None
    assert activated_subscription.status == "active"
    assert activated_subscription.starts_at is not None
    assert activated_subscription.expires_at is not None

    assert (
        before_activation
        <= activated_subscription.starts_at
        <= after_activation
    )

    expected_expires_at = (
        activated_subscription.starts_at
        + timedelta(days=plan.duration_days)
    )

    assert (
        activated_subscription.expires_at
        == expected_expires_at
    )