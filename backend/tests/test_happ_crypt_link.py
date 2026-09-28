import httpx
import pytest
from fastapi import HTTPException

from app.api.happ_connect import _import_link
from app.core.config import settings
from app.services import happ_crypt_link


def test_crypt5_pilot_encrypts_url_and_rejects_plaintext_fallback(monkeypatch):
    url = "https://connect.workplayvpn.ru/sub/private-test-token"
    monkeypatch.setattr(settings, "happ_crypt5_user_ids", "174")
    seen = []

    def post(endpoint, **kwargs):
        seen.append((endpoint, kwargs["json"]))
        return httpx.Response(
            200, text="happ://crypt5/ciphertext123",
            request=httpx.Request("POST", endpoint),
        )

    monkeypatch.setattr(happ_crypt_link.httpx, "post", post)
    assert _import_link(url, 174) == "happ://crypt5/ciphertext123"
    assert seen == [(happ_crypt_link.CRYPTO_API, {"url": url})]
    assert _import_link(url, 175) == f"happ://add/{url}"
    assert len(seen) == 1

    def bad_post(endpoint, **kwargs):
        return httpx.Response(
            200, text="happ://add/https://example.org/sub/private-test-token",
            request=httpx.Request("POST", endpoint),
        )

    monkeypatch.setattr(happ_crypt_link.httpx, "post", bad_post)
    with pytest.raises(HTTPException) as error:
        _import_link(url, 174)
    assert error.value.status_code == 503
    assert url not in error.value.detail


def test_crypt5_json_response(monkeypatch):
    monkeypatch.setattr(happ_crypt_link.httpx, "post", lambda endpoint, **kwargs:
        httpx.Response(200, json={"url": "happ://crypt5/abc123"},
                       request=httpx.Request("POST", endpoint)))
    assert happ_crypt_link.encrypted_happ_link("https://example.org/sub/t") == (
        "happ://crypt5/abc123"
    )
