from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select

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


def test_different_idempotency_keys_reuse_same_pending_payment(
    database,
) -> None:
    user = User(
        telegram_id=992000001,
        username="payment_creation_test",
        first_name="PaymentCreation",
        is_active=True,
    )

    database.add(user)
    database.commit()
    database.refresh(user)

    first_payment = payment_service.create_payment(
        database=database,
        telegram_id=user.telegram_id,
        plan_code="standard_1m",
        provider="test",
        idempotency_key="payment-create-key-a",
    )

    second_payment = payment_service.create_payment(
        database=database,
        telegram_id=user.telegram_id,
        plan_code="standard_1m",
        provider="test",
        idempotency_key="payment-create-key-b",
    )

    assert first_payment.id == second_payment.id
    assert first_payment.subscription_id == second_payment.subscription_id

    payment_count = database.scalar(
        select(func.count(Payment.id)).where(
            Payment.user_id == user.id,
            Payment.status == "pending",
        )
    )

    subscription_count = database.scalar(
        select(func.count(Subscription.id)).where(
            Subscription.user_id == user.id,
            Subscription.status == "pending",
        )
    )

    assert payment_count == 1
    assert subscription_count == 1


def test_different_plan_is_rejected_when_payment_pending(
    database,
) -> None:
    user = User(
        telegram_id=992000002,
        username="payment_creation_test_2",
        first_name="PaymentCreation2",
        is_active=True,
    )

    database.add(user)
    database.commit()
    database.refresh(user)

    plan_1m = database.scalar(
        select(Plan).where(
            Plan.code == "standard_1m",
        )
    )

    plan_3m = database.scalar(
        select(Plan).where(
            Plan.code == "standard_3m",
        )
    )

    assert plan_1m is not None
    assert plan_3m is not None

    first_payment = payment_service.create_payment(
        database=database,
        telegram_id=user.telegram_id,
        plan_code=plan_1m.code,
        provider="test",
        idempotency_key="payment-create-plan-a",
    )

    assert first_payment.status == "pending"
    assert first_payment.amount == Decimal("199.00")

    with pytest.raises(HTTPException) as exc_info:
        payment_service.create_payment(
            database=database,
            telegram_id=user.telegram_id,
            plan_code=plan_3m.code,
            provider="test",
            idempotency_key="payment-create-plan-b",
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "Payment already pending"

    payment_count = database.scalar(
        select(func.count(Payment.id)).where(
            Payment.user_id == user.id,
        )
    )

    pending_subscription_count = database.scalar(
        select(func.count(Subscription.id)).where(
            Subscription.user_id == user.id,
            Subscription.status == "pending",
        )
    )

    assert payment_count == 1
    assert pending_subscription_count == 1