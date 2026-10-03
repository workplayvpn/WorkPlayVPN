from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from app.db.session import Base
from app.models.location import Location
from app.models.vpn_node import VpnNode  # noqa: F401
from app.models.vpn_device import VpnDevice  # noqa: F401
from app.models.user import User
from app.models.plan import Plan
from app.models.subscription import Subscription
from app.models.payment import Payment
from app.models.device_activation import DeviceActivation
from app.models.support_ticket import SupportTicket
from app.models.abuse_alert import AbuseAlert
from app.services.abuse_observation import scan, RULES
from app.workers import informer

NOW = datetime(2026, 10, 3, 18, 0, tzinfo=UTC)


@pytest.fixture(scope='session', autouse=True)
def isolated_test_database():
    yield


@pytest.fixture
def db(monkeypatch):
    engine = create_engine('sqlite://')
    names = ('locations', 'users', 'plans', 'subscriptions', 'payments',
             'vpn_nodes', 'vpn_devices', 'device_activations', 'support_tickets', 'abuse_alerts')
    Base.metadata.create_all(engine, tables=[Base.metadata.tables[n] for n in names])
    factory = sessionmaker(engine, autoflush=False)
    monkeypatch.setattr(informer, 'SessionLocal', factory)
    monkeypatch.setattr(informer.settings, 'informer_bot_token', '12345:fake-test-token')
    monkeypatch.setattr(informer.settings, 'antifraud_observe_enabled', True)
    informer._accepted_alerts.clear()
    with factory() as session:
        session.add_all([
            Location(id=1, code='NL', name='NL'),
            User(id=1, telegram_id=555, username='customer', extra_device_slots=2),
            Plan(id=1, code='basic_month', name='Месяц', duration_days=30,
                 price_amount=Decimal('199'), currency='RUB', access_tier='basic', device_limit=3),
            Plan(id=2, code='trial_1d', name='Триал', duration_days=1,
                 price_amount=Decimal('0'), currency='RUB', access_tier='basic', device_limit=3),
            Subscription(id=1, user_id=1, plan_id=1, status='active',
                         expires_at=NOW+timedelta(days=30), created_at=NOW),
        ])
        session.commit()
        yield session
    informer._accepted_alerts.clear()
    engine.dispose()


def seed(db, model, count, when=NOW):
    for index in range(count):
        if model is Payment:
            row = Payment(id=index+1, user_id=1, subscription_id=1, provider='test',
                status='pending', idempotency_key=f'p-{index}', amount=Decimal('199'),
                currency='RUB', created_at=when)
        elif model is DeviceActivation:
            row = DeviceActivation(id=index+1, user_id=1, location_id=1,
                token_hash=f'{index:064x}', status='pending', expires_at=when+timedelta(hours=1),
                created_at=when)
        else:
            row = SupportTicket(id=str(index), user_id=1, category='other', tier='basic',
                network='wifi', description='Test', diagnostics={}, idempotency_key=str(index),
                created_at=when, updated_at=when)
        db.add(row)
    db.commit()


@pytest.mark.parametrize('rule,model,threshold,label', RULES)
def test_threshold_queues_one_alert_without_restricting_user(db, rule, model, threshold, label):
    seed(db, model, threshold)
    assert scan(db, NOW) == 1
    db.commit()
    event = db.scalar(select(AbuseAlert))
    assert event.rule == rule and label in event.text
    assert 'https://t.me/customer' in event.text and 'tg-555-' not in event.text
    assert 'не доказывает' in event.text
    user = db.get(User, 1)
    assert user.is_active and user.extra_device_slots == 2
    assert db.get(Subscription, 1).status == 'active'


@pytest.mark.parametrize('rule,model,threshold,label', RULES)
def test_below_threshold_is_quiet(db, rule, model, threshold, label):
    seed(db, model, threshold-1)
    assert scan(db, NOW) == 0


def test_cooldown_survives_new_session(db):
    seed(db, Payment, 8)
    assert scan(db, NOW) == 1
    db.commit()
    with informer.SessionLocal() as second:
        assert scan(second, NOW+timedelta(minutes=1)) == 0
        second.commit()
    assert len(db.scalars(select(AbuseAlert)).all()) == 1


def test_cooldown_expiry_allows_new_signal_for_new_activity(db):
    seed(db, Payment, 8)
    scan(db, NOW)
    db.commit()
    later = NOW+timedelta(hours=1, seconds=1)
    for payment in db.scalars(select(Payment)):
        payment.created_at = later
    db.commit()
    assert scan(db, later) == 1


def test_old_and_future_records_do_not_alert(db):
    seed(db, Payment, 8, NOW-timedelta(minutes=11))
    assert scan(db, NOW) == 0
    for p in db.scalars(select(Payment)):
        p.created_at = NOW+timedelta(minutes=1)
    db.commit()
    assert scan(db, NOW) == 0


def test_scan_rollback_does_not_leave_alert(db):
    seed(db, Payment, 8)
    assert scan(db, NOW) == 1
    db.rollback()
    assert db.scalar(select(AbuseAlert)) is None


@pytest.mark.parametrize('count,expected', [(1, 0), (2, 1)])
def test_duplicate_issued_trials(db, count, expected):
    for index in range(count):
        db.add(Subscription(id=index+2, user_id=1, plan_id=2, status='expired',
                           created_at=NOW-timedelta(minutes=index)))
    db.commit()
    assert scan(db, NOW) == expected


def test_no_username_is_not_an_invalid_profile_url(db):
    seed(db, Payment, 8)
    db.get(User, 1).username = None
    db.commit()
    scan(db, NOW)
    assert 'Профиль: публичный @username не указан' in db.scalar(select(AbuseAlert)).text


def enqueue(db):
    seed(db, Payment, 8)
    scan(db, NOW)
    db.commit()
    return db.scalar(select(AbuseAlert))


def test_disabled_has_no_scan_or_delivery(db, monkeypatch):
    seed(db, Payment, 8)
    monkeypatch.setattr(informer.settings, 'antifraud_observe_enabled', False)
    sender = Mock()
    monkeypatch.setattr(informer, 'send_message', sender)
    assert informer.scan_abuse_once() == 0
    assert not informer.process_alert_once()
    assert db.scalar(select(AbuseAlert)) is None
    sender.assert_not_called()


def test_alert_delivery_is_not_repeated(db, monkeypatch):
    event = enqueue(db)
    sender = Mock()
    monkeypatch.setattr(informer, 'send_message', sender)
    assert informer.process_alert_once()
    assert not informer.process_alert_once()
    assert sender.call_count == 1
    assert sender.call_args.args[0] == event.text
    db.expire_all()
    assert event.sent_at is not None


def test_telegram_failure_retries_without_recreating_alert(db, monkeypatch):
    event = enqueue(db)
    sender = Mock(side_effect=RuntimeError('offline'))
    monkeypatch.setattr(informer, 'send_message', sender)
    assert informer.process_alert_once()
    db.expire_all()
    assert event.sent_at is None and event.attempts == 1
    assert not informer.process_alert_once()
    event.next_attempt_at = datetime.now(UTC)-timedelta(seconds=1)
    db.commit()
    sender.side_effect = None
    assert informer.process_alert_once()
    db.expire_all()
    assert event.sent_at is not None
    assert len(db.scalars(select(AbuseAlert)).all()) == 1


def test_commit_failure_does_not_resend_alert(db, monkeypatch):
    event = enqueue(db)
    factory = informer.SessionLocal
    def failing_factory():
        session = factory()
        session.commit = Mock(side_effect=RuntimeError('commit unavailable'))
        return session
    sender = Mock()
    monkeypatch.setattr(informer, 'send_message', sender)
    monkeypatch.setattr(informer, 'SessionLocal', failing_factory)
    with pytest.raises(RuntimeError):
        informer.process_alert_once()
    monkeypatch.setattr(informer, 'SessionLocal', factory)
    assert informer.process_alert_once()
    assert sender.call_count == 1
    db.expire_all()
    assert event.sent_at is not None


def test_worker_scanner_uses_current_window(db, monkeypatch):
    seed(db, Payment, 8, datetime.now(UTC))
    assert informer.scan_abuse_once() == 1
    assert informer.scan_abuse_once() == 0


def test_standalone_worker_can_commit_alert():
    import subprocess
    import sys
    import os
    from pathlib import Path
    env = dict(os.environ, DATABASE_URL='sqlite://')
    env['PYTHONPATH'] = str(Path(__file__).resolve().parents[1])+os.pathsep+env.get('PYTHONPATH', '')
    script = """
from app.workers import informer
from app.db.session import engine
from sqlalchemy import text
from sqlalchemy.orm import Session
from datetime import datetime, UTC
with engine.begin() as c:
    c.execute(text('CREATE TABLE abuse_alerts (id VARCHAR PRIMARY KEY, user_id BIGINT, rule VARCHAR, text TEXT, attempts INTEGER, next_attempt_at DATETIME, created_at DATETIME, sent_at DATETIME)'))
    c.execute(text("INSERT INTO abuse_alerts VALUES ('x',1,'payment_burst','test',0,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP,NULL)"))
with Session(engine) as s:
    event = s.get(informer.AbuseAlert, 'x')
    event.sent_at = datetime.now(UTC)
    s.commit()
"""
    result = subprocess.run([sys.executable, '-c', script], env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr

def load_configurer():
    import importlib.util
    from pathlib import Path
    path = Path(__file__).resolve().parents[2] / 'ops' / 'configure_abuse_observation.py'
    spec = importlib.util.spec_from_file_location('observation_configurer', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_enabling_preserves_db_tls_and_private_token():
    import copy
    configure = load_configurer().configure
    data = {'services': {'informer-worker': {
        'environment': {'DATABASE_URL': 'private-db', 'INFORMER_BOT_TOKEN': '${INFORMER_BOT_TOKEN}'},
        'volumes': ['./root.crt:/root.crt:ro']}, 'backend': {'image': 'backend'}}}
    original = copy.deepcopy(data)
    result = configure(data, True)
    assert result['services']['informer-worker']['environment']['ANTIFRAUD_OBSERVE_ENABLED'] == 'true'
    environment = result['services']['informer-worker']['environment']
    assert environment['DATABASE_URL'] == 'private-db'
    assert environment['INFORMER_BOT_TOKEN'] == '${INFORMER_BOT_TOKEN}'
    assert result['services']['informer-worker']['volumes'] == ['./root.crt:/root.crt:ro']
    assert result['services']['backend'] == original['services']['backend']
    assert configure(result, True) == result


def test_disabling_leaves_informer_available():
    data = {'services': {'informer-worker': {'environment': {'DATABASE_URL': 'db'}}}}
    result = load_configurer().configure(data, False)
    assert result['services']['informer-worker']['environment'] == {
        'DATABASE_URL': 'db', 'ANTIFRAUD_OBSERVE_ENABLED': 'false'}


def test_configurer_rejects_missing_server_override():
    with pytest.raises(ValueError):
        load_configurer().configure({'services': {}}, True)
