"""Trial transaction and informer delivery tests; only an in-memory database."""
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock

import pytest
from fastapi import HTTPException
from sqlalchemy import Integer, create_engine, select, func
from sqlalchemy.orm import sessionmaker

from app.db.session import Base
from app.models.location import Location  # noqa: F401
from app.models.plan import Plan
from app.models.user import User
from app.models.subscription import Subscription
from app.models.payment import Payment  # noqa: F401
from app.models.subscription_token import SubscriptionToken  # noqa: F401
from app.models.informer_notification import InformerNotification
from app.services.informer import enqueue_trial
from app.services.subscription_service import SubscriptionService
from app.workers import informer


@pytest.fixture(scope="session", autouse=True)
def isolated_test_database():
    # Override the project PostgreSQL cleanup fixture for this isolated module.
    yield


@pytest.fixture
def db(monkeypatch):
    engine = create_engine("sqlite://")
    tables = [Base.metadata.tables[n] for n in (
        "locations", "users", "plans", "subscriptions", "payments",
        "subscription_tokens", "informer_notifications")]
    # SQLite autoincrement needs INTEGER; production retains BIGINT.
    monkeypatch.setattr(Subscription.__table__.c.id, "type", Integer())
    monkeypatch.setattr(Base.metadata.tables["subscription_tokens"].c.id, "type", Integer())
    Base.metadata.create_all(engine, tables=tables)
    factory = sessionmaker(engine, autoflush=False)
    monkeypatch.setattr(informer, "SessionLocal", factory)
    monkeypatch.setattr(informer.settings, "informer_bot_token", "123:fake")
    monkeypatch.setattr(informer.settings, "informer_owner_telegram_id", 555)
    # Other entitlement paths are outside this isolated activation test.
    monkeypatch.setattr(SubscriptionService, "get_active_subscription", lambda *a, **k: None)
    with factory() as session:
        session.add_all([
            User(id=1, telegram_id=555, username="customer", extra_device_slots=0),
            Plan(id=1, code="trial_1d", name="Пробный Basic", duration_days=1,
                 price_amount=Decimal("0"), currency="RUB", access_tier="basic",
                 device_limit=3, is_active=True),
        ])
        session.commit()
        yield session
    engine.dispose()


def event(db):
    return db.scalar(select(InformerNotification))


def activate(db):
    return SubscriptionService().create_trial(db, 1)


def test_new_trial_queues_without_telegram(db, monkeypatch):
    sender = Mock(side_effect=AssertionError("activation must not call Telegram"))
    monkeypatch.setattr(informer, "send_message", sender)
    subscription = activate(db)
    queued = event(db)
    assert subscription.status == "active"
    assert queued.event_key == "trial-activated:1"
    assert queued.payment_id is None
    assert "🎁 Активирован пробный Basic" in queued.text
    assert "Telegram ID: 555" in queued.text
    assert "https://t.me/customer" in queued.text
    assert "Срок: 24 ч" in queued.text
    assert "МСК" in queued.text
    assert "Платёж:" not in queued.text
    sender.assert_not_called()


def test_trial_cannot_activate_twice(db):
    activate(db)
    with pytest.raises(HTTPException) as exc:
        activate(db)
    assert exc.value.status_code == 409
    assert db.scalar(select(func.count()).select_from(InformerNotification)) == 1


def test_queue_idempotent_before_and_after_flush(db):
    user, plan = db.get(User, 1), db.get(Plan, 1)
    now = datetime(2026, 10, 10, 21, 0, tzinfo=UTC)
    subscription = Subscription(user_id=1, plan_id=1, status="active",
                                starts_at=now, expires_at=now + timedelta(days=1))
    enqueue_trial(db, user=user, subscription=subscription, plan=plan)
    enqueue_trial(db, user=user, subscription=subscription, plan=plan)
    db.flush()
    enqueue_trial(db, user=user, subscription=subscription, plan=plan)
    db.commit()
    assert db.scalar(select(func.count()).select_from(InformerNotification)) == 1
    assert "Активирован: 11.10.2026 00:00 МСК" in event(db).text


def test_queue_failure_rolls_back_trial(db, monkeypatch):
    import app.services.informer as service
    def fail(database, **kwargs):
        enqueue_trial(database, **kwargs)
        raise RuntimeError("queue failure")
    monkeypatch.setattr(service, "enqueue_trial", fail)
    with pytest.raises(RuntimeError, match="queue failure"):
        activate(db)
    assert db.scalar(select(func.count()).select_from(Subscription)) == 0
    assert event(db) is None


def test_commit_failure_rolls_back_trial_and_event(db, monkeypatch):
    monkeypatch.setattr(db, "commit", Mock(side_effect=RuntimeError("commit failure")))
    with pytest.raises(RuntimeError, match="commit failure"):
        activate(db)
    assert db.scalar(select(func.count()).select_from(Subscription)) == 0
    assert event(db) is None


def test_no_username(db):
    db.get(User, 1).username = None
    db.commit()
    activate(db)
    assert "Username: не указан" in event(db).text
    assert "https://t.me/" not in event(db).text


def test_delivery_with_retry_preserves_active_trial(db, monkeypatch):
    subscription = activate(db)
    monkeypatch.setattr(informer, "send_message", Mock(side_effect=RuntimeError("offline")))
    assert informer.process_once()
    db.expire_all()
    queued = event(db)
    assert queued.sent_at is None
    assert queued.attempts == 1
    assert db.get(Subscription, subscription.id).status == "active"
    queued.next_attempt_at = datetime.now(UTC) - timedelta(seconds=1)
    db.commit()
    sender = Mock()
    monkeypatch.setattr(informer, "send_message", sender)
    assert informer.process_once()
    assert not informer.process_once()
    sender.assert_called_once()
    assert "Ключ помощи:" in sender.call_args.args[0]
    db.expire_all()
    assert event(db).sent_at is not None


def test_old_trials_not_backfilled(db):
    now = datetime.now(UTC)
    db.add(Subscription(user_id=1, plan_id=1, status="active", starts_at=now,
                        expires_at=now + timedelta(days=1)))
    db.commit()
    with pytest.raises(HTTPException):
        activate(db)
    assert event(db) is None
