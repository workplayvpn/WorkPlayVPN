import json
from types import SimpleNamespace
from urllib.parse import urlencode

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
        }),
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

    monkeypatch.setattr(settings, "happ_auto_route_user_ids", "*")
    assert not route.auto_route_allowed(174)
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
    monkeypatch.setattr(
        route.subscription_token_service, "resolve_token_scope",
        lambda database, token: (SimpleNamespace(id=174), "mobile"),
    )
    monkeypatch.setattr(route, "active_entitlements", lambda db, user_id: {"mobile": True})
    device = SimpleNamespace(node_id=1, mobile_xray_uuid=CDN, mobile_xray_email="mobile@x")
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
    config = json.loads(response.body)
    assert len(config) == 1
    assert [item["tag"] for item in config[0]["outbounds"]] == [
        "vpn-direct", "vpn-cdn",
    ]
    assert config[0]["routing"]["balancers"][0]["fallbackTag"] == "vpn-cdn"


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


def test_network_display_feed_is_pilot_only(monkeypatch):
    monkeypatch.setattr(settings, "happ_auto_route_user_ids", "")
    monkeypatch.setattr(
        route.subscription_token_service, "resolve_token_scope",
        lambda database, token: (SimpleNamespace(id=174), "mobile"),
    )
    with pytest.raises(HTTPException) as exc:
        route.get_network_display_route("private-token", object())
    assert exc.value.status_code == 404


def test_network_display_feed_keeps_the_same_fallback(monkeypatch):
    monkeypatch.setattr(settings, "happ_auto_route_user_ids", "174")
    monkeypatch.setattr(
        route.subscription_token_service, "resolve_token_scope",
        lambda database, token: (SimpleNamespace(id=174), "mobile"),
    )
    monkeypatch.setattr(route, "active_entitlements", lambda db, user_id: {"mobile": True})
    device = SimpleNamespace(node_id=1, mobile_xray_uuid=CDN, mobile_xray_email="mobile@x")

    class Result:
        def __init__(self, value):
            self.value = value

        def all(self):
            return self.value

    class Database:
        calls = 0

        def scalars(self, query):
            self.calls += 1
            return Result([device] if self.calls == 1 else [SimpleNamespace(id=1)])

    monkeypatch.setattr(
        route.vpn_node_profile_service, "get_active_profiles_for_nodes",
        lambda **kwargs: ["ready"],
    )
    monkeypatch.setattr(route.subscription_builder, "build", lambda **kwargs: _links())
    response = route.get_network_display_route("private-token", Database())
    entries = json.loads(response.body)
    assert len(entries) == 2
    assert ["only WiFi" in entries[0]["remarks"],
            "only Mobile" in entries[1]["remarks"]] == [True, True]
    assert entries[0]["outbounds"] == entries[1]["outbounds"]
    assert entries[0]["routing"] == entries[1]["routing"]
