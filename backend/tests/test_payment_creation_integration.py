from decimal import Decimal
from datetime import UTC, datetime, timedelta

import pytest
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


def test_same_plan_reuses_pending_payment_for_different_keys(
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

    assert first_payment.status == "pending"
    assert second_payment.status == "pending"

    assert first_payment.expires_at is not None
    assert second_payment.expires_at is not None

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


def test_different_plan_is_allowed_when_payment_pending(
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

    second_payment = payment_service.create_payment(
        database=database,
        telegram_id=user.telegram_id,
        plan_code=plan_3m.code,
        provider="test",
        idempotency_key="payment-create-plan-b",
    )

    assert first_payment.id != second_payment.id

    assert first_payment.status == "pending"
    assert second_payment.status == "pending"

    assert first_payment.amount == Decimal("199.00")
    assert second_payment.amount == Decimal("499.00")

    assert first_payment.expires_at is not None
    assert second_payment.expires_at is not None

    payment_count = database.scalar(
        select(func.count(Payment.id)).where(
            Payment.user_id == user.id,
            Payment.status == "pending",
        )
    )

    pending_subscription_count = database.scalar(
        select(func.count(Subscription.id)).where(
            Subscription.user_id == user.id,
            Subscription.status == "pending",
        )
    )

    assert payment_count == 2
    assert pending_subscription_count == 2

@pytest.mark.parametrize("tier", ["basic", "mobile"])
def test_tariff_choice_keeps_independent_two_hour_invoices(database, monkeypatch, tier):
    monkeypatch.setattr("app.services.payment_service.mobile_pilot_allowed", lambda _: True)
    user = User(telegram_id=992010001 if tier == "basic" else 992010002,
                username="checkout_choice", first_name="Checkout", is_active=True)
    database.add(user)
    plans = [Plan(code=f"checkout_choice_{tier}_{days}", name=f"{tier} {days}",
                  duration_days=days, price_amount=Decimal(amount), currency="RUB",
                  access_tier=tier, device_limit=3, is_active=True)
             for days, amount in [(7, "99.00"), (30, "199.00")]]
    database.add_all(plans)
    database.commit()
    try:
        before = datetime.now(UTC)
        payments = [payment_service.create_payment(database, user.telegram_id, plan.code, "test",
                    idempotency_key=f"choice-{tier}-{plan.duration_days}") for plan in plans]
        assert payments[0].id != payments[1].id
        assert [p.amount for p in payments] == [Decimal("99.00"), Decimal("199.00")]
        assert all(p.status == "pending" for p in payments)
        assert all(before + timedelta(hours=2) <= p.expires_at <= datetime.now(UTC) + timedelta(hours=2)
                   for p in payments)
        resumed = payment_service.create_payment(database, user.telegram_id, plans[0].code, "test",
                    idempotency_key=f"choice-{tier}-back")
        assert resumed.id == payments[0].id
        payments[0].expires_at = datetime.now(UTC) - timedelta(seconds=1)
        database.commit()
        replacement = payment_service.create_payment(database, user.telegram_id, plans[0].code, "test",
                    idempotency_key=f"choice-{tier}-expired")
        assert replacement.id != payments[0].id
    finally:
        from sqlalchemy import delete
        database.execute(delete(User).where(User.id == user.id))
        database.commit()
        for plan in plans:
            database.delete(plan)
        database.commit()


def test_basic_checkout_cleanup_preserves_mobile_invoice(database, monkeypatch):
    monkeypatch.setattr("app.services.payment_service.mobile_pilot_allowed", lambda _: True)
    user = User(telegram_id=992010003, username="checkout_tiers", first_name="Checkout", is_active=True)
    database.add(user)
    plans = [Plan(code=f"checkout_cleanup_{tier}_{days}", name=f"{tier} {days}",
                  duration_days=days, price_amount=Decimal("199.00"), currency="RUB",
                  access_tier=tier, device_limit=3, is_active=True)
             for tier, days in [("basic", 7), ("basic", 30), ("mobile", 30)]]
    database.add_all(plans)
    database.commit()
    try:
        payments = [payment_service.create_payment(database, user.telegram_id, plan.code, "test",
                    idempotency_key=f"cleanup-{plan.code}") for plan in plans]
        payments[0].status = "succeeded"
        database.commit()
        payment_service._cancel_other_pending_payments(database, succeeded_payment=payments[0])
        database.expire_all()
        assert database.get(Payment, payments[1].id).status == "canceled"
        assert database.get(Payment, payments[2].id).status == "pending"
    finally:
        from sqlalchemy import delete
        database.execute(delete(User).where(User.id == user.id))
        database.commit()
        for plan in plans:
            database.delete(plan)
        database.commit()
