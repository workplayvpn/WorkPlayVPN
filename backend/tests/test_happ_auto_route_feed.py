import json
from datetime import UTC, datetime
from types import SimpleNamespace
from urllib.parse import quote, urlencode

from fastapi import HTTPException
import pytest

from app.api import happ_auto_route as route
from app.core.config import settings


DIRECT = "11111111-2222-4333-8444-555555555555"
CDN = "22222222-3333-4444-8555-666666666666"


def _links():
    return [
        f"vless://{DIRECT}@direct.example:443?" + urlencode({
            "type": "tcp", "security": "reality", "sni": "cover.example",
            "pbk": "public-key", "sid": "a1b2", "fp": "chrome",
        }) + "#" + quote("🇳🇱 Нидерланды — Wi-Fi", safe=""),
        f"vless://{CDN}@cdn.example:443?" + urlencode({
            "type": "xhttp", "security": "tls", "sni": "cdn.example",
            "path": "/relay/", "mode": "auto",
        }),
    ]


def test_auto_feed_is_closed_for_other_users_and_basic(monkeypatch):
    db = object()
    monkeypatch.setattr(settings, "happ_auto_route_user_ids", "")
    monkeypatch.setattr(
        route.subscription_token_service, "resolve_token_scope",
        lambda database, token: (SimpleNamespace(id=174), "mobile"),
    )
    with pytest.raises(HTTPException) as exc:
        route.get_auto_route("private-token", db)
    assert exc.value.status_code == 404
    with pytest.raises(HTTPException) as exc:
        route.get_routed_auto_route("private-token", db)
    assert exc.value.status_code == 404

    monkeypatch.setattr(settings, "happ_auto_route_user_ids", "*")
    assert route.auto_route_allowed(174)
    assert route.auto_route_allowed(175)
    monkeypatch.setattr(settings, "happ_auto_route_user_ids", "174")
    assert not route.auto_route_allowed(175)
    monkeypatch.setattr(settings, "happ_auto_route_user_ids", "174")
    monkeypatch.setattr(
        route.subscription_token_service, "resolve_token_scope",
        lambda database, token: (SimpleNamespace(id=174), "basic"),
    )
    with pytest.raises(HTTPException) as exc:
        route.get_auto_route("basic-token", db)
    assert exc.value.status_code == 404


def test_auto_feed_uses_separate_mobile_credential(monkeypatch):
    monkeypatch.setattr(settings, "happ_auto_route_user_ids", "174")
    monkeypatch.setattr(settings, "happ_smart_routing_user_ids", "174")
    monkeypatch.setattr(settings, "happ_provider_id", "provider-1")
    monkeypatch.setattr(settings, "happ_hidden_settings_user_ids", "174")
    monkeypatch.setattr(
        route.subscription_token_service, "resolve_token_scope",
        lambda database, token: (SimpleNamespace(id=174), "mobile"),
    )
    expiry = datetime(2026, 10, 27, 13, 15, tzinfo=UTC)
    monkeypatch.setattr(
        route, "active_entitlements",
        lambda db, user_id: {"mobile": (SimpleNamespace(expires_at=expiry), object())},
    )
    device = SimpleNamespace(node_id=1, public_id="WP-ABCDEF1234567890",
                             mobile_xray_uuid=CDN, mobile_xray_email="mobile@x")
    node = SimpleNamespace(id=1)

    class Result:
        def __init__(self, value):
            self.value = value

        def all(self):
            return self.value

    class Database:
        calls = 0

        def scalars(self, query):
            self.calls += 1
            return Result([device] if self.calls == 1 else [node])

    monkeypatch.setattr(
        route.vpn_node_profile_service, "get_active_profiles_for_nodes",
        lambda **kwargs: ["ready"],
    )
    monkeypatch.setattr(route.subscription_builder, "build", lambda **kwargs: _links())
    response = route.get_auto_route("private-token", Database())
    assert response.status_code == 200
    assert response.media_type == "application/json"
    assert response.headers["profile-title"] == "Work&PlayVPN Pro Auto (pilot)"
    assert response.headers["subscription-userinfo"] == f"expire={int(expiry.timestamp())}"
    assert response.headers["routing"].startswith("happ://routing/onadd/")
    config = json.loads(response.body)
    assert len(config) == 1
    assert [item["tag"] for item in config[0]["outbounds"]] == [
        "vpn-direct", "vpn-cdn",
    ]
    assert config[0]["routing"]["balancers"][0]["fallbackTag"] == "vpn-cdn"

    response = route.get_routed_auto_route("private-token", Database())
    assert response.headers["profile-title"] == "Work&PlayVPN Auto RU"
    assert response.headers["subscription-userinfo"] == f"expire={int(expiry.timestamp())}"
    routed = json.loads(response.body)[0]
    assert routed["remarks"] == "🇳🇱 Нидерланды"
    assert len(routed["outbounds"]) == 3
    assert routed["outbounds"][:2] == config[0]["outbounds"]
    assert routed["routing"]["rules"][0]["outboundTag"] == "ru-direct"
    assert routed["routing"]["rules"][-1] == config[0]["routing"]["rules"][0]

    branded = route.get_routed_mobile_subscription("private-token", Database())
    assert branded.headers["profile-title"] == "Work&PlayVPN Pro"
    assert branded.headers["announce"].startswith("base64:")
    assert branded.headers["providerid"] == "provider-1"
    assert branded.headers["hide-settings"] == "1"
    assert json.loads(branded.body)[0]["meta"]["serverDescription"] == "Work&PlayVPN Pro"


def test_auto_feed_rejects_expired_mobile_access(monkeypatch):
    monkeypatch.setattr(settings, "happ_auto_route_user_ids", "174")
    monkeypatch.setattr(
        route.subscription_token_service, "resolve_token_scope",
        lambda database, token: (SimpleNamespace(id=174), "mobile"),
    )
    monkeypatch.setattr(route, "active_entitlements", lambda db, user_id: {})
    with pytest.raises(HTTPException) as exc:
        route.get_auto_route("private-token", object())
    assert exc.value.status_code == 403
