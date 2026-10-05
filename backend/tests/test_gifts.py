"""Gift lifecycle without external payments/nodes; PG test checks real row locks."""
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import HTTPException, Response
from sqlalchemy import Integer, MetaData, create_engine, delete, func, select, text
from sqlalchemy.orm import Session

from app.main import app  # Load model registry; no external calls on import.
from app.core.config import settings
from app.db.session import Base
from app.models.user import User
from app.models.plan import Plan
from app.models.subscription import Subscription
from app.models.payment import Payment
from app.models.payment_fulfillment import PaymentFulfillment
from app.models.gift import GiftCertificate, GiftAttemptWindow
from app.models.informer_notification import InformerNotification
from app.services import gifts
from app.services.payment_service import payment_service
from app.services.subscription_service import subscription_service
from app.api.gifts import mine, catalog, owner


@pytest.fixture(scope="session", autouse=True)
def isolated_test_database():
    # SQLite cases are independent; the PG case explicitly verifies DB identity.
    yield


@pytest.fixture
def db(monkeypatch):
    metadata = MetaData()
    for source in Base.metadata.sorted_tables:
        table = source.to_metadata(metadata)
        if "id" in table.c and table.c.id.type.__class__.__name__ == "BigInteger":
            table.c.id.type = Integer()
    engine = create_engine("sqlite://")
    metadata.create_all(engine)
    monkeypatch.setattr(settings, "payment_mode", "test")
    monkeypatch.setattr(settings, "mobile_pilot_user_ids", "*")
    monkeypatch.setattr(subscription_service, "restore_user_access", Mock(return_value=[]))
    with Session(engine, autoflush=False) as session:
        session.add_all([User(id=1, telegram_id=101, username="buyer"),
                         User(id=2, telegram_id=102, username="recipient"), User(id=3, telegram_id=103),
                         Plan(id=1, code="standard_month", name="Basic месяц", duration_days=30,
                              device_limit=3, price_amount=199, currency="RUB", access_tier="basic"),
                         Plan(id=2, code="mobile_month", name="Mobile месяц", duration_days=30,
                              device_limit=3, price_amount=399, currency="RUB", access_tier="mobile")])
        session.commit()
        yield session
    engine.dispose()


def order(db, plan="standard_month", key=None):
    return payment_service.create_payment(db, 101, plan, "test", key or uuid.uuid4().hex, purchase_kind="gift")


def paid(db, plan="standard_month"):
    payment = order(db, plan)
    payment_service.mark_succeeded(db, payment.id)
    return db.scalar(select(GiftCertificate).where(GiftCertificate.payment_id == payment.id))


def auth(telegram_id):
    return SimpleNamespace(user=SimpleNamespace(id=telegram_id))


def count(db, model):
    return db.scalar(select(func.count()).select_from(model))


def test_pending_gift_has_no_code_or_buyer_access(db):
    payment = order(db)
    gift = db.scalar(select(GiftCertificate))
    assert payment.purpose == "gift" and gift.state == "pending" and gift.code_hash is None
    assert db.get(Subscription, payment.subscription_id).status == "pending"
    data = mine(Response(), auth(101), db)
    assert "code" not in data["purchased"][0]
    assert not data["activated"]


def test_paid_callback_is_idempotent_and_does_not_grant_buyer_or_referrals(db, monkeypatch):
    credit = Mock(side_effect=AssertionError("Gift must not earn referral credit"))
    monkeypatch.setattr("app.services.payment_service.credit_payment", credit)
    gift = paid(db)
    first_code = gifts.display_code(gift)
    payment_service.mark_succeeded(db, gift.payment_id)
    assert count(db, GiftCertificate) == 1 and count(db, InformerNotification) == 1
    assert count(db, PaymentFulfillment) == 1
    assert db.scalar(select(PaymentFulfillment)).status == "delivered"
    assert db.scalar(select(Subscription)).status == "completed"
    assert gift.state == "ready" and gifts.display_code(gift) == first_code
    assert "Куплен подарок" in db.scalar(select(InformerNotification)).text
    assert first_code not in db.scalar(select(InformerNotification)).text
    credit.assert_not_called()


def test_terms_are_snapshotted_and_private_plan_not_catalogue(db):
    payment = order(db)
    original = db.get(Plan, 1)
    original.duration_days, original.device_limit = 90, 8
    db.commit()
    payment_service.mark_succeeded(db, payment.id)
    gift = db.scalar(select(GiftCertificate))
    plan = db.get(Plan, gift.plan_id)
    assert (plan.duration_days, plan.device_limit, plan.is_active) == (30, 3, False)
    assert all(not item["code"].startswith("gift_") for item in catalog(auth(101), db))


def test_gift_code_normalization_and_high_entropy(db):
    gift = paid(db)
    assert len(gifts.raw_code(gift)) == 24
    code = " " + gifts.display_code(gift).lower().replace("-", " - ") + " "
    assert gifts.normalize_code(code) == gifts.raw_code(gift)
    assert gifts.preview_gift(db, 2, code)["duration_days"] == 30


def test_one_time_activation_preserves_tier_and_idempotent_retry(db):
    gift = paid(db)
    result = gifts.redeem_gift(db, 2, gifts.raw_code(gift))
    assert result["already_activated"] is False
    active = db.scalar(select(Subscription).where(Subscription.user_id == 2, Subscription.status == "active"))
    assert active and db.get(Plan, active.plan_id).access_tier == "basic"
    expires = active.expires_at
    assert gifts.redeem_gift(db, 2, gifts.raw_code(gift))["already_activated"] is True
    assert db.get(Subscription, active.id).expires_at == expires
    assert count(db, InformerNotification) == 2
    with pytest.raises(HTTPException) as error:
        gifts.redeem_gift(db, 3, gifts.raw_code(gift))
    db.rollback()
    assert error.value.status_code == 400
    assert db.get(GiftCertificate, gift.id).recipient_id == 2


def test_active_basic_is_extended_not_duplicated_and_mobile_unchanged(db):
    expiry = datetime.now(UTC) + timedelta(days=20)
    db.add_all([Subscription(id=80, user_id=2, plan_id=1, status="active", expires_at=expiry),
                Subscription(id=81, user_id=2, plan_id=2, status="active", expires_at=expiry)])
    db.commit()
    gift = paid(db)
    gifts.redeem_gift(db, 2, gifts.raw_code(gift))
    assert gifts.utc(db.get(Subscription, 80).expires_at) == expiry + timedelta(days=30)
    assert gifts.utc(db.get(Subscription, 81).expires_at) == expiry
    assert len(db.scalars(select(Subscription).where(Subscription.user_id == 2, Subscription.status == "active")).all()) == 2


def test_self_redemption_rejected_without_consuming(db):
    gift = paid(db)
    with pytest.raises(HTTPException) as error:
        gifts.redeem_gift(db, 1, gifts.raw_code(gift))
    db.rollback()
    assert error.value.status_code == 409 and db.get(GiftCertificate, gift.id).state == "ready"


def test_failed_provisioning_rolls_back_claim_and_notification(db, monkeypatch):
    gift = paid(db)
    monkeypatch.setattr(subscription_service, "restore_user_access", Mock(side_effect=RuntimeError("Node down")))
    with pytest.raises(RuntimeError):
        gifts.redeem_gift(db, 2, gifts.raw_code(gift))
    db.rollback()
    assert db.get(GiftCertificate, gift.id).state == "ready"
    assert not db.scalars(select(Subscription).where(Subscription.user_id == 2)).all()
    assert count(db, InformerNotification) == 1


def test_attempt_limit_survives_rollback_and_session_and_resets(db):
    for _ in range(10):
        with pytest.raises(HTTPException) as error:
            gifts.preview_gift(db, 2, "invalid")
        assert error.value.status_code == 400
        db.rollback()
    with Session(db.bind) as another:
        with pytest.raises(HTTPException) as error:
            gifts.preview_gift(another, 2, "invalid")
        assert error.value.status_code == 429
        another.rollback()
        window = another.get(GiftAttemptWindow, 2)
        assert window.attempts == 10
        window.started_at = datetime.now(UTC) - timedelta(minutes=16)
        another.commit()
        with pytest.raises(HTTPException) as error:
            gifts.preview_gift(another, 2, "invalid")
        assert error.value.status_code == 400
        assert another.get(GiftAttemptWindow, 2).attempts == 1


def test_mobile_pilot_checked_on_recipient_before_claim(db, monkeypatch):
    gift = paid(db, "mobile_month")
    monkeypatch.setattr(settings, "mobile_pilot_user_ids", "1")
    with pytest.raises(HTTPException) as error:
        gifts.redeem_gift(db, 2, gifts.raw_code(gift))
    db.rollback()
    assert error.value.status_code == 409 and db.get(GiftCertificate, gift.id).state == "ready"


def test_test_payment_gift_is_not_redeemable_in_live_mode(db, monkeypatch):
    gift = paid(db)
    monkeypatch.setattr(settings, "payment_mode", "live")
    with pytest.raises(HTTPException) as error:
        gifts.redeem_gift(db, 2, gifts.raw_code(gift))
    db.rollback()
    assert error.value.status_code == 409 and gift.state == "ready"


def test_owner_views_do_not_leak_codes_and_activation_view_has_no_code(db):
    gift = paid(db)
    response = Response()
    assert mine(response, auth(101), db)["purchased"][0]["code"] == gifts.display_code(gift)
    assert response.headers["cache-control"] == "no-store"
    assert mine(Response(), auth(103), db) == dict(purchased=[], activated=[], next_offset=None)
    gifts.redeem_gift(db, 2, gifts.raw_code(gift))
    assert "code" not in mine(Response(), auth(102), db)["activated"][0]
    assert "code" not in mine(Response(), auth(101), db)["purchased"][0]


def test_invalid_or_disabled_owner_cannot_access(db):
    with pytest.raises(HTTPException):
        owner(db, auth(999))
    db.get(User, 2).is_active = False
    db.commit()
    with pytest.raises(HTTPException):
        gifts.preview_gift(db, 2, "invalid")


def test_gift_payment_idempotency_does_not_cross_purposes(db):
    payment = order(db, key="gift-unique-key")
    assert order(db, key="gift-unique-key").id == payment.id and count(db, GiftCertificate) == 1
    with pytest.raises(HTTPException) as error:
        payment_service.create_payment(db, 101, "standard_month", "test", "gift-unique-key")
    assert error.value.status_code == 409


def test_pending_invoice_limit_serialized_per_buyer(db):
    for _ in range(5):
        order(db)
    with pytest.raises(HTTPException) as error:
        order(db)
    db.rollback()
    assert error.value.status_code == 429 and count(db, GiftCertificate) == 5


def test_daily_order_cap_applies_even_to_canceled_invoices(db):
    for _ in range(20):
        payment = order(db)
        payment.status = "canceled"
        db.commit()
    with pytest.raises(HTTPException) as error:
        order(db)
    db.rollback()
    assert error.value.status_code == 429 and count(db, GiftCertificate) == 20


def test_gift_invoice_not_visible_as_buyers_subscription(db):
    from app.api.mini_app import get_visible_subscription
    order(db)
    assert get_visible_subscription(db, db.get(User, 1)) is None
    from app.api.subscriptions import get_current_subscription
    with pytest.raises(HTTPException) as error:
        get_current_subscription(101, db)
    assert error.value.status_code == 404


def test_gift_cannot_be_delivered_as_buyers_device(db):
    from app.services.payment_fulfillment_service import payment_fulfillment_service
    gift = paid(db)
    fulfillment = db.scalar(select(PaymentFulfillment).where(PaymentFulfillment.payment_id == gift.payment_id))
    with pytest.raises(HTTPException) as error:
        payment_fulfillment_service.build_access(db, fulfillment)
    assert error.value.status_code == 409


def test_other_user_cannot_reuse_purchase_idempotency_key(db):
    order(db, key="private-gift-order-key")
    with pytest.raises(HTTPException) as error:
        payment_service.create_payment(db, 102, "standard_month", "test", "private-gift-order-key", purchase_kind="gift")
    assert error.value.status_code == 409


def test_gift_does_not_cancel_other_gift_or_subscription_invoice(db):
    normal = payment_service.create_payment(db, 101, "standard_month", "test", uuid.uuid4().hex)
    first, second = order(db), order(db)
    payment_service.mark_succeeded(db, first.id)
    assert db.get(Payment, normal.id).status == "pending"
    assert db.get(Payment, second.id).status == "pending"


def test_canceled_payment_cannot_issue_or_redeem(db):
    payment = order(db)
    gift = db.scalar(select(GiftCertificate))
    payment.status = "canceled"
    db.commit()
    with pytest.raises(HTTPException):
        payment_service.mark_succeeded(db, payment.id)
    db.rollback()
    with pytest.raises(HTTPException):
        gifts.validate_gift(db, gift, 2)
    assert gift.code_hash is None


def test_api_requires_telegram_auth():
    from fastapi.testclient import TestClient
    with TestClient(app) as client:
        response = client.get("/mini-app/gifts")
        assert response.status_code in (401, 403)


def test_postgres_simultaneous_redemption_has_one_winner(monkeypatch):
    from app.db.session import SessionLocal, engine
    if engine.dialect.name != "postgresql":
        pytest.skip("PostgreSQL required for concurrent FOR UPDATE proof")
    monkeypatch.setattr(settings, "payment_mode", "test")
    monkeypatch.setattr(subscription_service, "restore_user_access", Mock(return_value=[]))
    with SessionLocal() as db:
        assert db.scalar(text("SELECT current_database()")) == "workplayvpn_test"
        users = [User(telegram_id=700000000000 + int(uuid.uuid4().hex[:10], 16)) for _ in range(3)]
        db.add_all(users)
        plan = Plan(code="standard_gift_test_"+uuid.uuid4().hex[:12], name="Test", duration_days=30, device_limit=3, price_amount=199, currency="RUB", access_tier="basic")
        db.add(plan);db.commit()
        payment = payment_service.create_payment(db, users[0].telegram_id, plan.code, "test", uuid.uuid4().hex, purchase_kind="gift")
        payment_service.mark_succeeded(db, payment.id)
        gift = db.scalar(select(GiftCertificate).where(GiftCertificate.payment_id == payment.id))
        gift_id, code = gift.id, gifts.raw_code(gift)
        recipient_ids = [users[1].id, users[2].id]
        user_ids = [user.id for user in users]
        plan_ids = [plan.id, gift.plan_id]
    barrier = Barrier(2)
    def redeem(user_id):
        with SessionLocal() as db:
            barrier.wait(timeout=10)
            try:
                gifts.redeem_gift(db, user_id, code)
                return "ok"
            except HTTPException as error:
                db.rollback()
                return error.status_code
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            result = list(pool.map(redeem, recipient_ids))
        assert sorted(str(value) for value in result) == ["400", "ok"]
        with SessionLocal() as db:
            gift = db.get(GiftCertificate, gift_id)
            assert gift.state == "redeemed" and gift.recipient_id in recipient_ids
            assert db.scalar(select(func.count()).select_from(InformerNotification).where(InformerNotification.event_key == "gift:"+gift_id+":activated")) == 1
    finally:
        with SessionLocal() as db:
            db.execute(delete(GiftCertificate).where(GiftCertificate.id == gift_id))
            for model in (InformerNotification, PaymentFulfillment, Payment, Subscription, GiftAttemptWindow):
                db.execute(delete(model).where(model.user_id.in_(user_ids)))
            db.execute(delete(Plan).where(Plan.id.in_(plan_ids)))
            db.execute(delete(User).where(User.id.in_(user_ids)))
            db.commit()


def test_old_merchant_gift_invoice_stays_in_history_but_cannot_be_reused(db, monkeypatch):
    payment = order(db)
    payment.provider = "robokassa"
    payment.confirmation_url = "https://auth.robokassa.ru/Merchant/Index.aspx?MerchantLogin=old_shop&OutSum=199.00&InvId="+str(payment.id)+"&SignatureValue=old"
    db.commit()
    monkeypatch.setattr(settings, "robokassa_merchant_login", "new_shop")
    data = mine(Response(), auth(101), db)["purchased"][0]
    assert data["state"] == "obsolete" and data["confirmation_url"] is None
    assert db.get(Payment, payment.id).status == "pending"
    assert "code" not in data


def test_basic_30_days_new_shop_signed_callback_issues_gift(db, monkeypatch):
    from app.services.payment_providers.robokassa import RobokassaProvider, calculate_robokassa_signature
    from app.services.robokassa_webhook import robokassa_webhook_service
    for key, value in {"robokassa_merchant_login":"new_shop", "robokassa_password_1":"test_password_1",
                       "robokassa_password_2":"test_password_2", "robokassa_hash_algorithm":"md5",
                       "robokassa_is_test":True}.items():
        monkeypatch.setattr(settings, key, value)
    payment = order(db)
    # SQLite drops timestamptz; build the real provider URL without expiration here.
    result = RobokassaProvider().create_payment(amount=payment.amount, currency=payment.currency,
        description="Basic gift 30 days", idempotency_key=payment.idempotency_key,
        metadata={"payment_id":str(payment.id)})
    payment.provider="robokassa"
    payment.provider_payment_id=result.provider_payment_id
    payment.confirmation_url=result.confirmation_url
    db.commit()
    data = mine(Response(), auth(101), db)["purchased"][0]
    assert data["state"] == "pending" and data["confirmation_url"]
    payload = {"OutSum":"199.00", "InvId":str(payment.id)}
    payload["SignatureValue"] = calculate_robokassa_signature(parts=[payload["OutSum"],payload["InvId"],"test_password_2"],algorithm="md5")
    robokassa_webhook_service.verify_signature(payload)
    robokassa_webhook_service.handle_result(database=db, payload=payload)
    robokassa_webhook_service.handle_result(database=db, payload=payload)
    data = mine(Response(), auth(101), db)["purchased"][0]
    assert data["state"] == "ready" and data["code"]
    assert data["duration_days"] == 30 and data["access_tier"] == "basic"
    assert count(db, GiftCertificate) == 1
