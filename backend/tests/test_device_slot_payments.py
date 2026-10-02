from datetime import UTC, datetime, timedelta
from decimal import Decimal
import pytest
from fastapi import HTTPException
from sqlalchemy import select, delete
from app.db.session import SessionLocal
from app.models.user import User
from app.models.plan import Plan
from app.models.subscription import Subscription
from app.models.payment_fulfillment import PaymentFulfillment
from app.models.vpn_device import VpnDevice
from app.services.payment_service import payment_service
from app.services.device_slots import device_slot_offers
from app.services.entitlements import active_entitlements, shared_device_limit


@pytest.fixture
def db():
    with SessionLocal() as database:
        yield database
        database.rollback()
        database.execute(delete(User).where(User.telegram_id.between(990880001, 990880009)))
        database.commit()


def make_user(db, telegram_id=990880001, tier="basic", active=True):
    user = User(telegram_id=telegram_id, first_name="Slots", is_active=True)
    db.add(user)
    db.flush()
    if active:
        plan = db.scalar(select(Plan).where(Plan.code == ("standard_1m" if tier == "basic" else "mobile_1m")))
        sub = Subscription(user_id=user.id, plan_id=plan.id, status="active", starts_at=datetime.now(UTC), expires_at=datetime.now(UTC)+timedelta(days=12))
        db.add(sub)
    db.commit()
    return user


@pytest.mark.parametrize("count,price", [(1,249),(2,449),(3,649)])
def test_slots_apply_once_preserve_expiry_and_do_not_create_device(db,count,price):
    user = make_user(db)
    before = active_entitlements(db, user.id)["basic"][0].expires_at
    payment = payment_service.create_payment(db, user.telegram_id, f"device_slots_{count}", "test", f"slot-test-package-{count}")
    assert payment.amount == Decimal(price)
    assert user.extra_device_slots == 0
    same = payment_service.create_payment(db,user.telegram_id,f"device_slots_{count}","test",f"slot-test-package-{count}")
    assert same.id == payment.id
    payment_service.mark_succeeded(db,payment.id)
    payment_service.mark_succeeded(db,payment.id)
    db.refresh(user)
    assert user.extra_device_slots == count
    entitlements = active_entitlements(db,user.id)
    assert set(entitlements) == {"basic"}
    assert entitlements["basic"][0].expires_at == before
    assert shared_device_limit(entitlements,user.extra_device_slots) == 3+count
    assert db.scalar(select(VpnDevice.id).where(VpnDevice.user_id == user.id)) is None
    fulfillment = db.scalar(select(PaymentFulfillment).where(PaymentFulfillment.payment_id == payment.id))
    assert fulfillment.status == "delivered"


def test_slot_purchase_requires_live_subscription(db):
    user = make_user(db,active=False)
    with pytest.raises(HTTPException) as exc:
        payment_service.create_payment(db,user.telegram_id,"device_slots_1","test","slot-no-subscription")
    assert exc.value.status_code == 409


def test_canceled_slot_payment_cannot_increase_limit(db):
    user = make_user(db)
    payment = payment_service.create_payment(db,user.telegram_id,"device_slots_2","test","slot-canceled-payment")
    payment_service.mark_canceled(db,payment.id,telegram_id=user.telegram_id)
    with pytest.raises(HTTPException):
        payment_service.mark_succeeded(db,payment.id)
    db.refresh(user)
    assert user.extra_device_slots == 0


def test_mobile_only_slot_offers_use_shared_limit(db):
    user = make_user(db,tier="mobile")
    user.extra_device_slots = 4
    db.commit()
    offers = device_slot_offers(db,user.telegram_id)
    assert offers["total_limit"] == 7
    assert [o["new_limit"] for o in offers["offers"]] == [8,9,10]
    assert [Decimal(o["price_amount"]) for o in offers["offers"]] == [Decimal(249),Decimal(449),Decimal(649)]


def test_success_replay_repairs_record_without_readding_slots(db):
    user = make_user(db)
    payment = payment_service.create_payment(db,user.telegram_id,"device_slots_1","test","slot-repair-record")
    payment_service.mark_succeeded(db,payment.id)
    db.execute(delete(PaymentFulfillment).where(PaymentFulfillment.payment_id == payment.id))
    db.commit()
    payment_service.mark_succeeded(db,payment.id)
    db.refresh(user)
    assert user.extra_device_slots == 1
    record = db.scalar(select(PaymentFulfillment).where(PaymentFulfillment.payment_id == payment.id))
    assert record.status == "delivered"


def test_replay_with_stale_session_does_not_double_credit(db):
    from app.models.payment import Payment
    user = make_user(db)
    payment = payment_service.create_payment(db,user.telegram_id,"device_slots_1","test","slot-stale-session")
    with SessionLocal() as stale:
        cached_payment = stale.get(Payment, payment.id)
        cached_user = stale.get(User, user.id)
        assert cached_payment.status == "pending"
        payment_service.mark_succeeded(db,payment.id)
        payment_service.mark_succeeded(stale,payment.id)
        stale.refresh(cached_user)
        assert cached_user.extra_device_slots == 1


@pytest.mark.parametrize('tier', ['basic', 'mobile'])
def test_active_subscription_hides_trial_from_bot_catalogue(db, tier):
    from app.services.catalog import available_plans
    user = make_user(db, tier=tier)
    assert 'trial_1d' not in {plan.code for plan in available_plans(db, user.telegram_id, include_trial=True)}


def test_unused_trial_remains_available_to_new_user(db):
    from app.services.catalog import available_plans
    user = make_user(db, active=False)
    assert 'trial_1d' in {plan.code for plan in available_plans(db, user.telegram_id, include_trial=True)}
    trial = db.scalar(select(Plan).where(Plan.code == 'trial_1d'))
    db.add(Subscription(user_id=user.id, plan_id=trial.id, status='expired', starts_at=datetime.now(UTC)-timedelta(days=2), expires_at=datetime.now(UTC)-timedelta(days=1)))
    db.commit()
    assert 'trial_1d' not in {plan.code for plan in available_plans(db, user.telegram_id, include_trial=True)}
