from types import SimpleNamespace
from urllib.parse import parse_qs, unquote, urlparse

from app.services.client_profiles.happ import HappProfile


def make_profile(
    *,
    network: str,
    security: str,
    port: int,
    flow: str | None = None,
    server_name: str | None = None,
    settings: dict | None = None,
):
    return SimpleNamespace(
        node_id=1,
        protocol="vless",
        network=network,
        security=security,
        port=port,
        flow=flow,
        server_name=server_name,
        settings=settings,
        is_active=True,
    )


def test_happ_profile_builds_wifi_and_mobile_links() -> None:
    device = SimpleNamespace(
        xray_uuid="11111111-1111-1111-1111-111111111111",
    )
    node = SimpleNamespace(
        id=1,
        name="WorkPlayVPN-NL-01",
        host="203.0.113.10",
    )

    wifi_profile = make_profile(
        network="xhttp",
        security="tls",
        port=8443,
        server_name="nl1.workplayvpn.ru",
        settings={
            "path": "/wp",
            "mode": "auto",
            "fingerprint": "chrome",
        },
    )
    mobile_profile = make_profile(
        network="tcp",
        security="reality",
        port=443,
        flow="xtls-rprx-vision",
        server_name="speed.cloudflare.com",
        settings={
            "fingerprint": "chrome",
            "public_key": "test-public-key",
            "short_id": "test-short-id",
        },
    )

    links = HappProfile().build_links(
        device=device,
        nodes=[node],
        profiles=[
            mobile_profile,
            wifi_profile,
        ],
    )

    assert len(links) == 2

    wifi_url = urlparse(links[0])
    mobile_url = urlparse(links[1])

    assert unquote(wifi_url.fragment) == (
        "WorkPlayVPN-NL-01 — Wi-Fi"
    )
    assert unquote(mobile_url.fragment) == (
        "WorkPlayVPN-NL-01 — Mobile"
    )

    wifi_query = parse_qs(wifi_url.query)
    mobile_query = parse_qs(mobile_url.query)

    assert wifi_query["type"] == ["xhttp"]
    assert wifi_query["security"] == ["tls"]
    assert wifi_url.port == 8443

    assert mobile_query["type"] == ["tcp"]
    assert mobile_query["security"] == ["reality"]
    assert mobile_query["flow"] == ["xtls-rprx-vision"]
    assert mobile_url.port == 443