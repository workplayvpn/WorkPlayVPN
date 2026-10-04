"""Tier/device key isolation and authenticated QR delivery."""
import base64
from types import SimpleNamespace
from xml.etree import ElementTree

import pytest
import qrcode
from fastapi.testclient import TestClient

from app.api import mini_app
from app.api.telegram_webapp_auth import require_telegram_webapp_auth
from app.db.dependencies import get_db
from app.main import app
from app.core.config import settings
import httpx


@pytest.fixture
def key_client(monkeypatch):
    me = SimpleNamespace(
        subscriptions=[SimpleNamespace(access_tier=t, status="active") for t in ("basic", "mobile")],
        basic_device_connect_urls={"11": "https://connect.example/device/11/basic-owner-token"},
        auto_connect_urls={"11": "https://connect.example/auto/routed/device/11/mobile-owner-token"},
        connect_urls={"mobile": "https://connect.example/mobile-owner-token"},
        devices=SimpleNamespace(active_count=1),
    )
    monkeypatch.setattr(settings, "connect_base_url", "https://connect.example")
    monkeypatch.setattr(settings, "subscription_base_url", "https://feed.example/sub")
    me.crypto_inputs = []

    def encrypt(feed_url):
        me.crypto_inputs.append(feed_url)
        return "happ://crypt5/" + ("mobileCipher" if "mobile-owner-token" in feed_url else "basicCipher")

    monkeypatch.setattr(mini_app, "encrypted_happ_link", encrypt)
    monkeypatch.setattr(mini_app, "get_me", lambda **kwargs: me)
    previous = dict(app.dependency_overrides)
    app.dependency_overrides[require_telegram_webapp_auth] = lambda: SimpleNamespace(user=SimpleNamespace(id=123))
    app.dependency_overrides[get_db] = lambda: None
    yield TestClient(app), me
    app.dependency_overrides.clear()
    app.dependency_overrides.update(previous)


@pytest.mark.parametrize("tier", ["basic", "mobile"])
def test_key_qr_matches_selected_tier_and_device(key_client, tier, monkeypatch):
    client, me = key_client
    encoded_values = []
    original_add_data = qrcode.QRCode.add_data

    def capture_data(code, value, **kwargs):
        encoded_values.append(value)
        return original_add_data(code, value, **kwargs)

    monkeypatch.setattr(qrcode.QRCode, "add_data", capture_data)
    response = client.get(f"/mini-app/keys/{tier}?device_id=11")
    assert response.status_code == 200
    data = response.json()
    links = me.basic_device_connect_urls if tier == "basic" else me.auto_connect_urls
    expected_feed = links["11"].replace("https://connect.example/", "https://feed.example/sub/", 1)
    assert me.crypto_inputs == [expected_feed]
    assert data["url"] == "happ://crypt5/" + ("basicCipher" if tier == "basic" else "mobileCipher")
    assert "owner-token" not in response.text
    assert "https://feed.example" not in response.text
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "X-Telegram-Init-Data"
    svg = base64.b64decode(data["qr_data_url"].split(",", 1)[1])
    assert ElementTree.fromstring(svg).tag.endswith("svg")
    assert encoded_values == [data["url"]]
    assert ElementTree.fromstring(svg).find("{http://www.w3.org/2000/svg}path") is not None


@pytest.mark.parametrize("tier", ["basic", "mobile"])
@pytest.mark.parametrize("device_id", [12, -1, 999999])
def test_other_or_deleted_device_cannot_get_key(key_client, tier, device_id):
    client, _ = key_client
    response = client.get(f"/mini-app/keys/{tier}?device_id={device_id}")
    assert response.status_code == 404
    assert "owner-token" not in response.text


@pytest.mark.parametrize("tier", ["basic", "mobile"])
def test_expired_tier_cannot_get_key(key_client, tier):
    client, me = key_client
    me.subscriptions = [item for item in me.subscriptions if item.access_tier != tier]
    assert client.get(f"/mini-app/keys/{tier}?device_id=11").status_code == 403


@pytest.mark.parametrize("tier", ["basic", "mobile"])
def test_device_selection_required_for_device_keys(key_client, tier):
    client, _ = key_client
    assert client.get(f"/mini-app/keys/{tier}").status_code == 409


def test_legacy_mobile_shared_link(key_client):
    client, me = key_client
    me.auto_connect_urls = {}
    response = client.get("/mini-app/keys/mobile")
    assert response.status_code == 200
    assert response.json()["url"] == "happ://crypt5/mobileCipher"
    assert me.crypto_inputs == ["https://feed.example/sub/mobile-owner-token"]
    me.devices.active_count = 0
    assert client.get("/mini-app/keys/mobile").status_code == 409


def test_unknown_tier_and_invalid_device_id(key_client):
    client, _ = key_client
    assert client.get("/mini-app/keys/pro?device_id=11").status_code == 404
    assert client.get("/mini-app/keys/basic?device_id=abc").status_code == 422


def test_key_route_requires_telegram_auth():
    assert TestClient(app).get("/mini-app/keys/basic?device_id=11").status_code == 401


@pytest.mark.parametrize("failure", [ValueError("bad response"), httpx.TimeoutException("timeout")])
def test_crypto_failure_does_not_return_plaintext_or_instruction(key_client, monkeypatch, failure):
    client, _ = key_client

    def fail(url):
        raise failure

    monkeypatch.setattr(mini_app, "encrypted_happ_link", fail)
    response = client.get("/mini-app/keys/basic?device_id=11")
    assert response.status_code == 503
    assert "owner-token" not in response.text
    assert "https://" not in response.text


def test_unexpected_instruction_origin_is_not_sent_to_crypto(key_client):
    client, me = key_client
    me.basic_device_connect_urls["11"] = "https://other.example/device/11/token"
    assert client.get("/mini-app/keys/basic?device_id=11").status_code == 503
    assert me.crypto_inputs == []
