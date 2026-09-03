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


def test_successful_payment_creates_single_fulfillment(
    database,
) -> None:
    from sqlalchemy import func

    from app.models.payment_fulfillment import PaymentFulfillment

    user = User(
        telegram_id=991000003,
        username="integration_fulfillment",
        first_name="Fulfillment",
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
        provider="cloudpayments",
        provider_payment_id=None,
        idempotency_key="integration-fulfillment-001",
        status="pending",
        amount=Decimal("199.00"),
        currency="RUB",
        confirmation_url=None,
    )

    database.add(payment)
    database.commit()

    payment_id = payment.id

    first_result = payment_service.mark_succeeded(
        database=database,
        payment_id=payment_id,
        provider_payment_id="cp-fulfillment-001",
    )

    assert first_result.status == "succeeded"

    first_count = database.scalar(
        select(func.count(PaymentFulfillment.id)).where(
            PaymentFulfillment.payment_id == payment_id,
        )
    )

    assert first_count == 1

    fulfillment = database.scalar(
        select(PaymentFulfillment).where(
            PaymentFulfillment.payment_id == payment_id,
        )
    )

    assert fulfillment is not None
    assert fulfillment.user_id == user.id
    assert fulfillment.status == "pending"
    assert fulfillment.attempts == 0
    assert fulfillment.device_id is None
    assert fulfillment.delivered_at is None

    second_result = payment_service.mark_succeeded(
        database=database,
        payment_id=payment_id,
        provider_payment_id="cp-fulfillment-001",
    )

    assert second_result.status == "succeeded"

    second_count = database.scalar(
        select(func.count(PaymentFulfillment.id)).where(
            PaymentFulfillment.payment_id == payment_id,
        )
    )

    assert second_count == 1


def test_successful_payment_cancels_other_pending_payments(
    database,
) -> None:
    user = User(
        telegram_id=991000004,
        username="integration_multiple_payments",
        first_name="MultiplePayments",
        is_active=True,
    )

    database.add(user)
    database.commit()
    database.refresh(user)

    first_payment = payment_service.create_payment(
        database=database,
        telegram_id=user.telegram_id,
        plan_code="standard_3m",
        provider="test",
        idempotency_key="multiple-payment-3m",
    )

    second_payment = payment_service.create_payment(
        database=database,
        telegram_id=user.telegram_id,
        plan_code="standard_6m",
        provider="test",
        idempotency_key="multiple-payment-6m",
    )

    first_payment_id = first_payment.id
    first_subscription_id = (
        first_payment.subscription_id
    )

    second_payment_id = second_payment.id
    second_subscription_id = (
        second_payment.subscription_id
    )

    result = payment_service.mark_succeeded(
        database=database,
        payment_id=second_payment_id,
        provider_payment_id=(
            second_payment.provider_payment_id
        ),
    )

    assert result.status == "succeeded"

    database.expire_all()

    first_payment = database.get(
        Payment,
        first_payment_id,
    )

    second_payment = database.get(
        Payment,
        second_payment_id,
    )

    first_subscription = database.get(
        Subscription,
        first_subscription_id,
    )

    second_subscription = database.get(
        Subscription,
        second_subscription_id,
    )

    assert first_payment is not None
    assert second_payment is not None
    assert first_subscription is not None
    assert second_subscription is not None

    assert first_payment.status == "canceled"
    assert second_payment.status == "succeeded"

    assert first_subscription.status == "canceled"
    assert second_subscription.status == "active"


def test_repeated_success_cancels_leftover_pending_payment(
    database,
) -> None:
    user = User(
        telegram_id=991000005,
        username="integration_repeated_cleanup",
        first_name="RepeatedCleanup",
        is_active=True,
    )

    database.add(user)
    database.commit()
    database.refresh(user)

    succeeded_payment = payment_service.create_payment(
        database=database,
        telegram_id=user.telegram_id,
        plan_code="standard_3m",
        provider="test",
        idempotency_key="repeated-cleanup-paid",
    )

    payment_service.mark_succeeded(
        database=database,
        payment_id=succeeded_payment.id,
        provider_payment_id=(
            succeeded_payment.provider_payment_id
        ),
    )

    leftover_payment = payment_service.create_payment(
        database=database,
        telegram_id=user.telegram_id,
        plan_code="standard_6m",
        provider="test",
        idempotency_key="repeated-cleanup-leftover",
    )

    leftover_payment_id = leftover_payment.id
    leftover_subscription_id = (
        leftover_payment.subscription_id
    )

    result = payment_service.mark_succeeded(
        database=database,
        payment_id=succeeded_payment.id,
        provider_payment_id=(
            succeeded_payment.provider_payment_id
        ),
    )

    assert result.status == "succeeded"

    database.expire_all()

    leftover_payment = database.get(
        Payment,
        leftover_payment_id,
    )

    leftover_subscription = database.get(
        Subscription,
        leftover_subscription_id,
    )

    assert leftover_payment is not None
    assert leftover_subscription is not None

    assert leftover_payment.status == "canceled"
    assert leftover_subscription.status == "canceled"
