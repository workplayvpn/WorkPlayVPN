from datetime import UTC, datetime, timedelta
from itertools import count
from types import SimpleNamespace
from urllib.parse import quote, urlencode
import json

import pytest
from sqlalchemy import delete, select
from starlette.requests import Request

from app.api.subscription_feed import get_subscription_feed
from app.core.config import settings
from app.db.session import SessionLocal
from app.models.location import Location
from app.models.plan import Plan
from app.models.payment import Payment
from app.models.subscription import Subscription
from app.models.user import User
from app.models.vpn_device import VpnDevice
from app.models.vpn_node import VpnNode
from app.services import subscription_service as subscription_module
from app.services import payment_service as payment_module
from app.services.entitlements import active_entitlements
from app.services.device_activation_service import device_activation_service
from app.services.subscription_builder import subscription_builder
from app.services.subscription_service import subscription_service
from app.services.payment_service import payment_service
from app.services.subscription_token_service import subscription_token_service
from app.services.vpn_node_profile_service import vpn_node_profile_service
from app.services.xray_node import xray_node_service


_counter = count(1)


@pytest.fixture
def account(monkeypatch):
    marker = next(_counter)
    telegram_id = 995610000 + marker
    node_code = f"dual-test-{marker}"
    events = []
    monkeypatch.setattr(subscription_module, "require_mobile_profile", lambda db, node_id: None)
    monkeypatch.setattr(
        xray_node_service, "add_mobile_user",
        lambda node, email, user_uuid: events.append(("add_mobile", email)),
    )
    monkeypatch.setattr(
        xray_node_service, "remove_mobile_user",
        lambda node, email: events.append(("remove_mobile", email)),
    )
    monkeypatch.setattr(
        xray_node_service, "remove_device",
        lambda node, device: events.append(("remove_device", device.id)),
    )
    monkeypatch.setattr(
        xray_node_service, "add_device",
        lambda node, device: events.append(("add_device", device.id)),
    )
    with SessionLocal() as db:
        location = db.scalar(select(Location).where(Location.code == "NL"))
        basic = db.scalar(select(Plan).where(Plan.code == "standard_1m"))
        mobile = db.scalar(select(Plan).where(Plan.code == "mobile_1m"))
        assert location and basic and mobile
        user = User(telegram_id=telegram_id, first_name="Dual test")
        node = VpnNode(
            location_id=location.id, code=node_code, name="Dual test node",
            host="192.0.2.56", ssh_user="test", is_active=True,
        )
        db.add_all([user, node])
        db.flush()
        basic_sub = Subscription(
            user_id=user.id, plan_id=basic.id, status="active",
            starts_at=datetime.now(UTC),
            expires_at=datetime.now(UTC) + timedelta(days=20),
        )
        mobile_purchase = Subscription(
            user_id=user.id, plan_id=mobile.id, status="pending",
        )
        device = VpnDevice(
            user_id=user.id, node_id=node.id, device_name="Phone",
            xray_uuid=f"f52a5e6a-4800-4a3d-b47b-{marker:012x}",
            xray_email=f"dual_{marker}@workplayvpn", is_active=True,
        )
        db.add_all([basic_sub, mobile_purchase, device])
        db.commit()
        yield db, user.id, basic_sub.id, mobile_purchase.id, device.id, events
        db.execute(delete(User).where(User.id == user.id))
        db.execute(delete(VpnNode).where(VpnNode.code == node_code))
        db.commit()


def test_paid_basic_and_mobile_have_independent_clocks(account):
    db, user_id, basic_id, mobile_id, device_id, events = account
    basic_before = db.get(Subscription, basic_id).expires_at
    mobile = subscription_service.activate_subscription(db, db.get(Subscription, mobile_id))
    assert mobile.id == mobile_id
    assert db.get(Subscription, basic_id).expires_at == basic_before
    assert set(active_entitlements(db, user_id)) == {"basic", "mobile"}
    assert [action for action, _ in events] == ["add_mobile"]

    subscription_service.activate_subscription(db, db.get(Subscription, mobile_id))
    assert len(events) == 1  # repeated payment notification

    subscription_service.expire_subscription(db, db.get(Subscription, basic_id))
    assert db.get(Subscription, mobile_id).status == "active"
    assert db.get(VpnDevice, device_id).mobile_xray_email
    assert len(events) == 1  # Direct still belongs to Mobile Wi-Fi

    subscription_service.expire_subscription(db, db.get(Subscription, mobile_id))
    assert events[-1] == ("remove_device", device_id)


def test_paid_basic_does_not_block_mobile_checkout(account, monkeypatch):
    db, user_id, basic_id, _, _, _ = account
    mobile_plan = db.scalar(select(Plan).where(Plan.code == "mobile_1m"))
    original_active = mobile_plan.is_active
    monkeypatch.setattr(payment_module, "mobile_pilot_allowed", lambda user_id: True)
    mobile_plan.is_active = True
    db.commit()
    try:
        telegram_id = db.get(User, user_id).telegram_id
        payment = payment_service.create_payment(
            db, telegram_id, "mobile_1m", "test",
            idempotency_key=f"dual-checkout-{user_id}-first",
        )
        assert isinstance(payment, Payment)
        assert db.get(Subscription, payment.subscription_id).plan_id == mobile_plan.id
        assert db.get(Subscription, basic_id).status == "active"
    finally:
        mobile_plan.is_active = original_active
        db.commit()


def test_mobile_expiry_only_revokes_cdn_when_basic_is_live(account):
    db, _, basic_id, mobile_id, device_id, events = account
    subscription_service.activate_subscription(db, db.get(Subscription, mobile_id))
    mobile_email = db.get(VpnDevice, device_id).mobile_xray_email
    events.clear()

    subscription_service.expire_subscription(db, db.get(Subscription, mobile_id))
    assert events == [("remove_mobile", mobile_email)]
    assert db.get(VpnDevice, device_id).mobile_xray_email is None
    assert db.get(Subscription, basic_id).status == "active"

    subscription_service.expire_subscription(db, db.get(Subscription, basic_id))
    assert events[-1] == ("remove_device", device_id)


def test_new_activation_reconciles_expired_mobile_without_revoking_basic(account):
    db, user_id, basic_id, mobile_id, device_id, events = account
    subscription_service.activate_subscription(db, db.get(Subscription, mobile_id))
    mobile = db.get(Subscription, mobile_id)
    mobile.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    email = db.get(VpnDevice, device_id).mobile_xray_email
    db.commit()
    events.clear()

    activation, _ = device_activation_service.create_activation(
        db, db.get(User, user_id).telegram_id, "NL",
    )
    assert activation.status == "pending"
    assert db.get(Subscription, mobile_id).status == "expired"
    assert db.get(Subscription, basic_id).status == "active"
    assert events == [("remove_mobile", email)]


def test_new_activation_reconciles_expired_basic_without_revoking_mobile(account):
    db, user_id, basic_id, mobile_id, _, events = account
    subscription_service.activate_subscription(db, db.get(Subscription, mobile_id))
    basic = db.get(Subscription, basic_id)
    basic.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    db.commit()
    events.clear()

    activation, _ = device_activation_service.create_activation(
        db, db.get(User, user_id).telegram_id, "NL",
    )
    assert activation.status == "pending"
    assert db.get(Subscription, basic_id).status == "expired"
    assert db.get(Subscription, mobile_id).status == "active"
    assert events == []


def test_basic_can_be_bought_while_mobile_is_active(account):
    db, user_id, basic_id, mobile_id, device_id, events = account
    basic = db.get(Subscription, basic_id)
    mobile = db.get(Subscription, mobile_id)
    basic.status = "pending"
    mobile.status = "active"
    mobile.starts_at = datetime.now(UTC)
    mobile.expires_at = datetime.now(UTC) + timedelta(days=17)
    device = db.get(VpnDevice, device_id)
    device.mobile_xray_uuid = "2bf4b310-921d-4d90-bf13-3090e87c3898"
    device.mobile_xray_email = "existing-mobile@workplayvpn"
    db.commit()
    mobile_before = mobile.expires_at

    result = subscription_service.activate_subscription(db, basic)
    assert result.id == basic_id
    assert db.get(Subscription, mobile_id).expires_at == mobile_before
    assert set(active_entitlements(db, user_id)) == {"basic", "mobile"}
    assert events == []  # Mobile already registered the shared Direct credential


def test_failed_mobile_provision_keeps_paid_basic(account, monkeypatch):
    db, _, basic_id, mobile_id, device_id, events = account
    basic_before = db.get(Subscription, basic_id).expires_at

    def fail(*, node, email, user_uuid):
        raise RuntimeError("CDN unavailable")

    monkeypatch.setattr(xray_node_service, "add_mobile_user", fail)
    with pytest.raises(RuntimeError, match="CDN unavailable"):
        subscription_service.activate_subscription(db, db.get(Subscription, mobile_id))
    db.expire_all()
    assert db.get(Subscription, basic_id).expires_at == basic_before
    assert db.get(Subscription, mobile_id).status == "pending"
    assert db.get(VpnDevice, device_id).mobile_xray_uuid is None
    assert events == []


def test_scoped_happ_feeds_never_mix_basic_and_mobile(account, monkeypatch):
    db, user_id, basic_id, mobile_id, _, _ = account
    subscription_service.activate_subscription(db, db.get(Subscription, mobile_id))
    _, basic_token = subscription_token_service.get_or_create_token(
        db, db.get(User, user_id).telegram_id,
    )
    token_record, _ = subscription_token_service.get_or_create_token(
        db, db.get(User, user_id).telegram_id,
    )
    mobile_token = subscription_token_service.scoped_token(token_record, "mobile")
    assert basic_token != mobile_token
    assert subscription_token_service.resolve_token_scope(db, basic_token)[1] == "basic"
    assert subscription_token_service.resolve_token_scope(db, mobile_token)[1] == "mobile"

    seen = []
    def build(**kwargs):
        seen.append(kwargs["include_happ_mobile"])
        return ["vless://wifi", "vless://mobile"] if seen[-1] else ["vless://basic"]
    monkeypatch.setattr(subscription_builder, "build", build)
    request = Request({
        "type": "http", "method": "GET", "path": "/sub/",
        "headers": [(b"user-agent", b"happ/1.0")],
    })
    basic_feed = get_subscription_feed(basic_token, request, db)
    mobile_feed = get_subscription_feed(mobile_token, request, db)
    assert seen == [False, True]
    assert basic_feed.headers["profile-title"] == "Work&PlayVPN Basic"
    assert mobile_feed.headers["profile-title"] == "Work&PlayVPN Mobile"
    assert basic_feed.headers["subscription-userinfo"] == (
        f"expire={int(db.get(Subscription, basic_id).expires_at.timestamp())}"
    )
    assert mobile_feed.headers["subscription-userinfo"] == (
        f"expire={int(db.get(Subscription, mobile_id).expires_at.timestamp())}"
    )

    subscription_service.expire_subscription(db, db.get(Subscription, basic_id))
    assert get_subscription_feed(basic_token, request, db).status_code == 403
    assert get_subscription_feed(mobile_token, request, db).status_code == 200


def test_pilot_mobile_feed_refreshes_to_one_routed_happ_configuration(account, monkeypatch):
    db, user_id, _, mobile_id, device_id, _ = account
    subscription_service.activate_subscription(db, db.get(Subscription, mobile_id))
    token_record, basic_token = subscription_token_service.get_or_create_token(
        db, db.get(User, user_id).telegram_id,
    )
    mobile_token = subscription_token_service.scoped_token(token_record, "mobile")
    monkeypatch.setattr(settings, "happ_auto_route_user_ids", "")
    monkeypatch.setattr(
        vpn_node_profile_service, "get_active_profiles_for_nodes",
        lambda **kwargs: [SimpleNamespace(
            code="test-reality", protocol="vless", network="tcp",
            security="reality", port=443,
        )],
    )

    def links(*, device, include_happ_mobile, **kwargs):
        direct = f"vless://{device.xray_uuid}@direct.example:443?" + urlencode({
            "type": "tcp", "security": "reality", "sni": "cover.example",
            "pbk": "public-key", "fp": "chrome",
        }) + "#" + quote("🇳🇱 Нидерланды — Wi-Fi", safe="")
        if not include_happ_mobile:
            return [direct]
        cdn = f"vless://{device.mobile_xray_uuid}@cdn.example:443?" + urlencode({
            "type": "xhttp", "security": "tls", "sni": "cdn.example",
            "path": "/relay/",
        })
        return [direct, cdn]

    monkeypatch.setattr(subscription_builder, "build", links)
    request = Request({
        "type": "http", "method": "GET", "path": "/sub/",
        "headers": [(b"user-agent", b"happ/1.0")],
    })
    legacy = get_subscription_feed(mobile_token, request, db)
    assert legacy.status_code == 200
    assert legacy.headers["content-type"].startswith("text/plain")

    monkeypatch.setattr(settings, "happ_auto_route_user_ids", str(user_id))
    mobile = get_subscription_feed(mobile_token, request, db)
    assert mobile.status_code == 200
    assert mobile.headers["content-type"].startswith("application/json")
    assert mobile.headers["profile-title"] == "Work&PlayVPN Mobile"
    assert mobile.headers["subscription-userinfo"] == (
        f"expire={int(db.get(Subscription, mobile_id).expires_at.timestamp())}"
    )
    config = json.loads(mobile.body)
    assert len(config) == 1
    assert config[0]["remarks"] == "🇳🇱 Нидерланды"
    assert [item["tag"] for item in config[0]["outbounds"]] == [
        "vpn-direct", "vpn-cdn", "ru-direct",
    ]
    assert config[0]["outbounds"][1]["settings"]["vnext"][0]["users"][0]["id"] == (
        db.get(VpnDevice, device_id).mobile_xray_uuid
    )
    basic = get_subscription_feed(basic_token, request, db)
    assert basic.status_code == 200
    assert basic.headers["content-type"].startswith("text/plain")
    assert basic.headers["profile-title"] == "Work&PlayVPN Basic"
