"""Shared subscription keys register physical installations, not key copies."""
import base64
import uuid
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import Integer, MetaData, create_engine, func, select
from sqlalchemy.orm import Session

from app.api import happ_auto_route, subscription_feed
from app.core.config import settings
from app.db.dependencies import get_db
from app.models.location import Location
from app.models.plan import Plan
from app.models.subscription import Subscription
from app.models.user import User
from app.models.vpn_device import VpnDevice
from app.models.vpn_node import VpnNode
from app.services import happ_account_device as service
from app.services.happ_device_metadata import hwid_digest
from app.services.vpn_device_service import vpn_device_service
from app.services.xray_node import xray_node_service


def headers(hwid="installation-one", model="iPhone"):
    return {"user-agent": "Happ/5.9.0", "x-hwid": hwid,
            "x-device-model": model, "x-device-os": "iOS", "x-ver-os": "27.0"}


@pytest.fixture
def account_db(monkeypatch):
    # Local relational tests, independent of production/test DB credentials.
    metadata = MetaData()
    models = (Location, User, Plan, Subscription, VpnNode, VpnDevice)
    for model in models:
        table = model.__table__.to_metadata(metadata)
        table.c.id.type = Integer()
    engine = create_engine("sqlite://")
    metadata.create_all(engine)
    db = Session(engine, autoflush=False)
    loc = Location(id=1, code="nl", name="Netherlands")
    user = User(id=1, telegram_id=123, preferred_location_id=1)
    node = VpnNode(id=1, location_id=1, code="nl-one", name="NL",
                   host="example.test", ssh_user="test")
    db.add_all([loc, user, node])
    for number, tier in enumerate(("basic", "mobile"), 1):
        db.add(Plan(id=number, code=tier, name=tier, access_tier=tier,
                    duration_days=30, price_amount=199, currency="RUB", device_limit=3))
        db.add(Subscription(id=number, user_id=1, plan_id=number, status="active"))
    db.commit()
    calls = []
    monkeypatch.setattr(service.subscription_service, "expire_stale_subscriptions",
                        lambda *args: False)
    import app.services.vpn_device_service as creation
    monkeypatch.setattr(creation, "require_mobile_profile", lambda *args: None)
    monkeypatch.setattr(xray_node_service, "add_user",
                        lambda **kwargs: calls.append("basic") or str(uuid.uuid4()))
    monkeypatch.setattr(xray_node_service, "add_mobile_user",
                        lambda **kwargs: calls.append("mobile"))
    monkeypatch.setattr(xray_node_service, "remove_device",
                        lambda **kwargs: calls.append("remove"))
    yield db, user, calls
    db.close()
    engine.dispose()


def count(db):
    return db.scalar(select(func.count(VpnDevice.id)).where(VpnDevice.is_active.is_(True)))


def test_shared_key_registers_new_device_and_reuses_it_for_both_tiers(account_db):
    db, user, calls = account_db
    one = service.resolve_happ_account_device(db, user.id, "basic", headers())
    assert one.happ_hwid_digest == hwid_digest("installation-one")
    assert one.happ_device_model == "iPhone"
    assert one.happ_device_os == "iOS 27.0"
    assert one.client_instance_id == one.happ_hwid_digest
    assert "installation-one" not in vars(one).values()
    again = service.resolve_happ_account_device(db, user.id, "mobile", headers())
    assert again.id == one.id
    assert count(db) == 1 and calls == ["basic", "mobile"]
    two = service.resolve_happ_account_device(db, user.id, "basic", headers("two"))
    assert two.id != one.id and two.xray_uuid != one.xray_uuid
    assert two.mobile_xray_uuid != one.mobile_xray_uuid
    assert count(db) == 2


def test_unknown_device_cannot_take_first_legacy_credential(account_db):
    db, user, _ = account_db
    existing = vpn_device_service.create_device(db, user.telegram_id, "nl-one", "Old")
    new = service.resolve_happ_account_device(db, user.id, "basic", headers())
    assert new.id != existing.id and new.xray_uuid != existing.xray_uuid
    assert existing.happ_hwid_digest is None


def test_old_device_link_can_bind_an_unidentified_owned_device(account_db):
    db, user, calls = account_db
    existing = vpn_device_service.create_device(db, user.telegram_id, "nl-one", "Old")
    resolved = service.resolve_happ_account_device(db, user.id, "basic", headers(),
                                                 device_id=existing.id)
    assert resolved.id == existing.id and count(db) == 1
    with pytest.raises(HTTPException) as exc:
        service.resolve_happ_account_device(db, user.id, "basic", headers("stranger"),
                                            device_id=existing.id)
    assert exc.value.status_code == 403


def test_shared_limit_blocks_fourth_device_but_allows_existing_refresh(account_db):
    db, user, calls = account_db
    for i in range(3):
        service.resolve_happ_account_device(db, user.id, "basic", headers(str(i)))
    before = list(calls)
    with pytest.raises(HTTPException) as exc:
        service.resolve_happ_account_device(db, user.id, "mobile", headers("four"))
    assert exc.value.status_code == 409 and calls == before
    service.resolve_happ_account_device(db, user.id, "mobile", headers("0"))
    assert count(db) == 3
    user.extra_device_slots = 1
    db.commit()
    service.resolve_happ_account_device(db, user.id, "mobile", headers("four"))
    assert count(db) == 4


@pytest.mark.parametrize("hwid", ["", " ", "x" * 257, "bad\x00id"])
def test_missing_or_invalid_hwid_never_returns_any_device(account_db, hwid):
    db, user, calls = account_db
    with pytest.raises(HTTPException) as exc:
        service.resolve_happ_account_device(db, user.id, "basic", headers(hwid))
    assert exc.value.status_code == 403 and count(db) == 0 and calls == []


@pytest.mark.parametrize("tier", ["basic", "mobile"])
def test_removed_device_stays_revoked_even_with_free_slots(account_db, tier):
    db, user, calls = account_db
    one = service.resolve_happ_account_device(db, user.id, tier, headers())
    vpn_device_service.remove_device(db, user.telegram_id, one.id)
    before = list(calls)
    for _ in range(3):
        with pytest.raises(HTTPException) as exc:
            service.resolve_happ_account_device(db, user.id, tier, headers())
        assert exc.value.status_code == 403 and "Device was removed" in exc.value.detail
    assert count(db) == 0 and calls == before
    assert not db.get(VpnDevice, one.id).is_active


def test_removed_individual_device_link_stays_revoked(account_db):
    db, user, calls = account_db
    one = service.resolve_happ_account_device(db, user.id, "basic", headers())
    vpn_device_service.remove_device(db, user.telegram_id, one.id)
    with pytest.raises(HTTPException) as exc:
        service.resolve_happ_account_device(db, user.id, "basic", headers(), device_id=one.id)
    assert exc.value.status_code == 403 and "Device was removed" in exc.value.detail
    assert count(db) == 0


def test_new_installation_can_use_a_slot_freed_by_another_revoked_device(account_db):
    db, user, calls = account_db
    one = service.resolve_happ_account_device(db, user.id, "basic", headers())
    vpn_device_service.remove_device(db, user.telegram_id, one.id)
    other = service.resolve_happ_account_device(db, user.id, "basic", headers("another"))
    assert other.id != one.id and other.xray_uuid != one.xray_uuid and count(db) == 1


def test_other_accounts_cannot_bind_a_foreign_device(account_db):
    db, user, _ = account_db
    db.add(User(id=2, telegram_id=456))
    foreign = VpnDevice(id=30, user_id=2, node_id=1, device_name="Foreign",
                        xray_uuid=str(uuid.uuid4()), xray_email="foreign@test")
    db.add(foreign)
    db.commit()
    with pytest.raises(HTTPException) as exc:
        service.resolve_happ_account_device(db, user.id, "basic", headers(), device_id=30)
    assert exc.value.status_code == 404


def test_inactive_subscription_never_creates_device(account_db):
    db, user, calls = account_db
    db.get(Subscription, 1).status = "expired"
    db.commit()
    with pytest.raises(HTTPException) as exc:
        service.resolve_happ_account_device(db, user.id, "basic", headers())
    assert exc.value.status_code == 403 and calls == []


@pytest.fixture
def feed_client(account_db, monkeypatch):
    db, user, _ = account_db
    monkeypatch.setattr(settings, "happ_account_device_registration_enabled", True)
    monkeypatch.setattr(settings, "happ_auto_route_user_ids", "*")
    monkeypatch.setattr(settings, "happ_smart_routing_user_ids", "")
    monkeypatch.setattr(settings, "happ_provider_id", "")
    monkeypatch.setattr(subscription_feed.subscription_token_service, "resolve_token_scope",
                        lambda database, raw_token: (user, "mobile" if "mobile" in raw_token else "basic"))
    monkeypatch.setattr(subscription_feed.vpn_node_profile_service,
                        "get_active_profiles_for_nodes", lambda **kwargs: [])
    def build(**kwargs):
        device = kwargs["device"]
        links = [f"vless://{device.xray_uuid}@direct.test:443?type=tcp&security=reality"]
        if kwargs["include_happ_mobile"]:
            links.append(f"vless://{device.mobile_xray_uuid}@cdn.test:443?type=ws&security=tls&path=/relay")
        return links
    monkeypatch.setattr(subscription_feed.subscription_builder, "build", build)
    monkeypatch.setattr(happ_auto_route, "build_routed_auto_config",
                        lambda *links: [{"links": list(links)}])
    monkeypatch.setattr(happ_auto_route, "build_auto_route_config",
                        lambda *links: [{"links": list(links)}])
    app = FastAPI()
    app.include_router(happ_auto_route.router)
    app.include_router(subscription_feed.router)
    app.dependency_overrides[get_db] = lambda: db
    # Same thread is required for the isolated in-memory SQLite session.
    from starlette.requests import Request
    def get(path, request_headers):
        request = Request({"type": "http", "headers": [
            (k.encode(), v.encode()) for k, v in request_headers.items()]})
        if path.startswith("/sub/auto/routed/"):
            return happ_auto_route.get_routed_auto_route("mobile", db, request)
        if path.startswith("/sub/auto/"):
            return happ_auto_route.get_auto_route("mobile", db, request)
        return subscription_feed.get_subscription_feed(path.split("/")[-1], request, db)
    return get, db


@pytest.mark.parametrize("path", ["/sub/basic", "/sub/mobile", "/sub/auto/routed/mobile", "/sub/auto/mobile"])
def test_every_shared_feed_returns_own_credentials_and_registers_new_device(feed_client, path):
    get, db = feed_client
    first = get(path, headers("first"))
    second = get(path, headers("second"))
    assert first.status_code == second.status_code == 200
    devices = db.scalars(select(VpnDevice).order_by(VpnDevice.id)).all()
    assert len(devices) == 2
    body = second.body if "mobile" in path else base64.b64decode(second.body)
    assert devices[1].xray_uuid.encode() in body
    assert devices[0].xray_uuid.encode() not in body
    assert get(path, headers("second")).status_code == 200 and count(db) == 2
    with pytest.raises(HTTPException) as exc:
        get(path, {})
    assert exc.value.status_code == 403


@pytest.mark.parametrize("same_hwid", [True, False])
def test_postgres_concurrent_imports_serialize_the_last_slot(monkeypatch, same_hwid):
    """Real row-lock test, executed by the project's PostgreSQL test container."""
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from sqlalchemy import delete, text
    from app.db.session import SessionLocal, engine

    if engine.dialect.name != "postgresql":
        pytest.skip("PostgreSQL row locks require the project test database")
    with SessionLocal() as db:
        assert db.scalar(text("SELECT current_database()")) == "workplayvpn_test"
        loc = db.scalar(select(Location).where(Location.is_active.is_(True)))
        assert loc is not None
        suffix = uuid.uuid4().hex
        plan = Plan(code="hwid-"+suffix, name="HWID race test", access_tier="basic",
                    duration_days=30, price_amount=1, currency="RUB", device_limit=1,
                    is_active=False)
        node = VpnNode(location_id=loc.id, code="hwid-"+suffix, name="test",
                       host="localhost", ssh_user="test")
        user = User(telegram_id=900000000000 + int(suffix[:8], 16),
                    preferred_location_id=loc.id)
        db.add_all([plan, node, user])
        db.flush()
        db.add(Subscription(user_id=user.id, plan_id=plan.id, status="active"))
        db.commit()
        user_id, node_id, plan_id = user.id, node.id, plan.id

    monkeypatch.setattr(service.subscription_service, "expire_stale_subscriptions",
                        lambda *args: False)
    monkeypatch.setattr(xray_node_service, "add_user", lambda **kwargs: str(uuid.uuid4()))
    # Restrict provisioning to our test node, avoiding any real SSH calls.
    original_create = vpn_device_service.create_device
    def create(**kwargs):
        kwargs["node_code"] = "hwid-"+suffix
        return original_create(**kwargs)
    monkeypatch.setattr(vpn_device_service, "create_device", create)
    barrier = Barrier(2)
    def enroll(hwid):
        with SessionLocal() as db:
            barrier.wait(timeout=10)
            try:
                return service.resolve_happ_account_device(db, user_id, "basic", headers(hwid)).id
            except HTTPException as exc:
                return -exc.status_code
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(enroll, "first"),
                       pool.submit(enroll, "first" if same_hwid else "second")]
            results = [future.result(timeout=20) for future in futures]
        if same_hwid:
            assert results[0] == results[1] and results[0] > 0
        else:
            assert sum(result > 0 for result in results) == 1 and -409 in results
        with SessionLocal() as db:
            assert db.scalar(select(func.count(VpnDevice.id)).where(
                VpnDevice.user_id == user_id, VpnDevice.is_active.is_(True))) == 1
    finally:
        with SessionLocal() as db:
            db.execute(delete(VpnDevice).where(VpnDevice.user_id == user_id))
            db.execute(delete(Subscription).where(Subscription.user_id == user_id))
            db.execute(delete(User).where(User.id == user_id))
            db.execute(delete(VpnNode).where(VpnNode.id == node_id))
            db.execute(delete(Plan).where(Plan.id == plan_id))
            db.commit()


@pytest.mark.parametrize("path", ["/sub/basic", "/sub/mobile", "/sub/auto/routed/mobile", "/sub/auto/mobile"])
def test_full_account_returns_notice_without_credentials_then_recovers(feed_client, path):
    import json
    from app.services.happ_device_limit_response import LIMIT_MESSAGE
    get, db = feed_client
    for hwid in ["first", "second", "third"]:
        assert get(path, headers(hwid)).status_code == 200
    response = get(path, headers("fourth"))
    assert response.status_code == 200 and count(db) == 3
    assert base64.b64decode(response.headers["announce"].split(":", 1)[1]).decode() == LIMIT_MESSAGE
    config = json.loads(response.body)[0]
    assert config["outbounds"] == [{"tag": "blocked", "protocol": "blackhole", "settings": {}}]
    assert "vless" not in response.body.decode() and "uuid" not in response.body.decode()
    # Existing installations still receive their real profile at full capacity.
    assert b'blackhole' not in get(path, headers("first")).body
    user = db.get(User, 1)
    user.extra_device_slots = 1
    db.commit()
    assert b'blackhole' not in get(path, headers("fourth")).body
    assert count(db) == 4


@pytest.mark.parametrize("path", ["/sub/basic", "/sub/mobile", "/sub/auto/routed/mobile", "/sub/auto/mobile"])
def test_removed_device_feed_replaces_credentials_with_notice_without_reenrollment(feed_client, path):
    import json
    from app.services.happ_device_limit_response import REMOVED_MESSAGE
    get, db = feed_client
    assert get(path, headers("first")).status_code == 200
    device = db.scalar(select(VpnDevice).where(VpnDevice.is_active.is_(True)))
    old_uuid, old_mobile_uuid = device.xray_uuid, device.mobile_xray_uuid
    vpn_device_service.remove_device(db, db.get(User, 1).telegram_id, device.id)
    for _ in range(3):
        response = get(path, headers("first"))
        assert response.status_code == 200 and count(db) == 0
        assert base64.b64decode(response.headers["announce"].split(":", 1)[1]).decode() == REMOVED_MESSAGE
        config = json.loads(response.body)[0]
        assert config["remarks"] == "Устройство заблокировано"
        assert config["outbounds"] == [{"tag": "blocked", "protocol": "blackhole", "settings": {}}]
        assert old_uuid.encode() not in response.body and old_mobile_uuid.encode() not in response.body
        assert b'vless' not in response.body
    # Increasing capacity must not undo a deliberate deletion.
    db.get(User, 1).extra_device_slots = 3
    db.commit()
    assert b'blackhole' in get(path, headers("first")).body and count(db) == 0
    assert b'blackhole' not in get(path, headers("second")).body and count(db) == 1


def test_unrelated_errors_are_not_converted_to_blocked_profiles():
    from app.services.happ_device_limit_response import is_device_limit_error, is_device_removed_error
    for error in [HTTPException(403, "Active subscription required"),
                  HTTPException(409, "Ambiguous device registration"),
                  HTTPException(502, "VPN node unavailable")]:
        assert not is_device_limit_error(error) and not is_device_removed_error(error)
