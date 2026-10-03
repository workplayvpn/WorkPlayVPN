from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock
import httpx
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from app.db.session import Base
from app.models.location import Location  # noqa: F401
from app.models.user import User
from app.models.plan import Plan
from app.models.subscription import Subscription
from app.models.payment import Payment
from app.models.subscription_token import SubscriptionToken
from app.models.informer_notification import InformerNotification
from app.services.informer import enqueue_purchase
from app.services.help_access import key_for
from app.workers import informer


@pytest.fixture(scope='session', autouse=True)
def isolated_test_database():
    # This module uses its own SQLite DB; never touches the project's database.
    yield


@pytest.fixture
def db(monkeypatch):
    engine = create_engine('sqlite://')
    tables = [Base.metadata.tables[n] for n in ('locations', 'users', 'plans', 'subscriptions', 'payments', 'subscription_tokens', 'informer_notifications')]
    Base.metadata.create_all(engine, tables=tables)
    factory = sessionmaker(engine, autoflush=False)
    monkeypatch.setattr(informer, 'SessionLocal', factory)
    monkeypatch.setattr(informer.settings, 'informer_bot_token', '12345:fake-test-token')
    monkeypatch.setattr(informer.settings, 'informer_owner_telegram_id', 2027613435)
    with factory() as session:
        session.add_all([User(id=1, telegram_id=555, username='customer', extra_device_slots=2),
            Plan(id=1, code='mobile_month', name='Месяц', duration_days=30, price_amount=Decimal('399'), currency='RUB', access_tier='mobile', device_limit=3),
            Subscription(id=1, user_id=1, plan_id=1, status='active', expires_at=datetime.now(UTC)+timedelta(days=30)),
            Payment(id=1, user_id=1, subscription_id=1, provider='test', status='succeeded', idempotency_key='test', amount=Decimal('399'), currency='RUB'),
            SubscriptionToken(id=1, user_id=1, version=1)])
        session.commit()
        yield session
    engine.dispose()


def queue(db):
    enqueue_purchase(db, db.get(Payment, 1))
    db.commit()
    return db.scalar(select(InformerNotification))


def test_snapshot_and_idempotency(db):
    event = queue(db)
    enqueue_purchase(db, db.get(Payment, 1))
    db.commit()
    assert len(db.scalars(select(InformerNotification)).all()) == 1
    assert 'ТЕСТОВАЯ ОПЛАТА' in event.text and '@customer' in event.text
    assert '30 дней' in event.text and 'Mobile' in event.text
    assert 'tg-555-' not in event.text


def test_pending_payment_not_queued(db):
    db.get(Payment, 1).status = 'pending'
    enqueue_purchase(db, db.get(Payment, 1))
    db.commit()
    assert not db.scalars(select(InformerNotification)).all()


def test_rollback_does_not_queue(db):
    enqueue_purchase(db, db.get(Payment, 1))
    db.flush()
    db.rollback()
    assert not db.scalars(select(InformerNotification)).all()


def test_slots_snapshot(db):
    plan = db.get(Plan, 1)
    plan.code = 'device_slots_2'
    plan.access_tier = 'device_slots'
    db.flush()
    event = queue(db)
    assert 'Куплено устройств: +2' in event.text
    assert 'Новый общий лимит: 5' in event.text


def test_delivery_and_no_repeat(db, monkeypatch):
    queue(db)
    sender = Mock()
    monkeypatch.setattr(informer, 'send_message', sender)
    assert informer.process_once()
    assert not informer.process_once()
    assert key_for(db.get(User, 1), db.get(SubscriptionToken, 1)) in sender.call_args.args[0]
    assert sender.call_count == 1
    db.expire_all()
    assert db.scalar(select(InformerNotification)).sent_at


def test_failure_is_retained_and_retried(db, monkeypatch):
    event = queue(db)
    sender = Mock(side_effect=RuntimeError('offline'))
    monkeypatch.setattr(informer, 'send_message', sender)
    assert informer.process_once()
    db.expire_all()
    assert event.sent_at is None and event.attempts == 1
    assert not informer.process_once()
    event.next_attempt_at = datetime.now(UTC)-timedelta(seconds=1)
    db.commit()
    sender.side_effect = None
    assert informer.process_once()
    db.expire_all()
    assert event.sent_at and event.attempts == 2


def test_disabled_worker_has_no_effect(db, monkeypatch):
    event = queue(db)
    monkeypatch.setattr(informer.settings, 'informer_bot_token', None)
    assert not informer.process_once()
    assert event.attempts == 0 and event.sent_at is None


def test_only_owner_receives_message(monkeypatch):
    client = Mock()
    client.__enter__ = Mock(return_value=client)
    client.__exit__ = Mock(return_value=False)
    client.post.return_value.status_code = 200
    client.post.return_value.json.return_value = {'ok': True}
    monkeypatch.setattr(informer.httpx, 'Client', Mock(return_value=client))
    monkeypatch.setattr(informer.settings, 'informer_bot_token', '12345:private-token')
    monkeypatch.setattr(informer.settings, 'informer_owner_telegram_id', 2027613435)
    informer.send_message('purchase')
    payload = client.post.call_args.kwargs['json']
    assert payload['chat_id'] == 2027613435 and 'parse_mode' not in payload


def test_transport_error_does_not_expose_token(monkeypatch):
    monkeypatch.setattr(informer.settings, 'informer_bot_token', '12345:private-token')
    monkeypatch.setattr(informer.httpx, 'Client', Mock(side_effect=httpx.ConnectError('https://api.telegram.org/bot12345:private-token')))
    with pytest.raises(RuntimeError) as error:
        informer.send_message('purchase')
    assert 'private-token' not in str(error.value)


def test_delivered_hook_queues_in_same_transaction(db):
    from app.services.payment_fulfillment_service import payment_fulfillment_service
    from types import SimpleNamespace
    fulfillment = SimpleNamespace(payment_id=1, status='processing')
    payment_fulfillment_service.mark_delivered(database=db, fulfillment=fulfillment)
    assert fulfillment.status == 'delivered'
    assert db.scalar(select(InformerNotification)).payment_id == 1


def test_compose_patch_preserves_local_db_and_is_idempotent():
    import importlib.util
    from pathlib import Path
    path = Path(__file__).resolve().parents[2] / 'ops' / 'configure_informer_compose.py'
    spec = importlib.util.spec_from_file_location('informer_compose', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    original = 'services:\n  payment-fulfillment-worker:\n    environment:\n      DATABASE_URL: custom-external-db\n    command: ["old"]\n  caddy:\n    image: caddy\nvolumes:\n  data:\n'
    result = module.configure(original)
    assert 'DATABASE_URL: custom-external-db' in result and '  caddy:\n    image: caddy' in result
    assert result.count('  informer-worker:') == 1
    assert module.configure(result) == result
