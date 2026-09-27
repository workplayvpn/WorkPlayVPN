from urllib.parse import urlencode

import pytest

from app.services.happ_auto_route import (
    build_auto_route_config,
    build_network_display_configs,
)


DIRECT = "11111111-2222-4333-8444-555555555555"
CDN = "22222222-3333-4444-8555-666666666666"


def links() -> tuple[str, str]:
    direct = "vless://" + DIRECT + "@direct.example:443?" + urlencode({
        "type": "tcp", "security": "reality", "sni": "cover.example",
        "pbk": "public-key", "sid": "a1b2", "fp": "chrome",
    })
    cdn = "vless://" + CDN + "@cdn.example:443?" + urlencode({
        "type": "xhttp", "security": "tls", "sni": "cdn.example",
        "path": "/relay/", "mode": "auto", "host": "cdn.example",
        "extra": '{"headers":{"X-Test":"probe"}}',
    })
    return direct, cdn


def test_local_probe_prefers_direct_and_only_falls_back_to_cdn() -> None:
    config = build_auto_route_config(*links())[0]
    routes = config["outbounds"]
    assert [item["tag"] for item in routes] == ["vpn-direct", "vpn-cdn"]
    assert config["observatory"]["subjectSelector"] == ["vpn-direct"]
    assert config["routing"]["balancers"] == [{
        "tag": "prefer-direct", "selector": ["vpn-direct"],
        "fallbackTag": "vpn-cdn", "strategy": {"type": "leastPing"},
    }]
    assert routes[0]["settings"]["vnext"][0]["users"][0]["id"] == DIRECT
    assert routes[1]["settings"]["vnext"][0]["users"][0]["id"] == CDN
    assert routes[1]["streamSettings"]["xhttpSettings"]["extra"] == {
        "headers": {"X-Test": "probe"},
    }


def test_rejects_missing_or_shared_cdn_credential() -> None:
    direct, cdn = links()
    with pytest.raises(ValueError):
        build_auto_route_config(direct, cdn.replace(CDN, DIRECT))
    with pytest.raises(ValueError):
        build_auto_route_config(direct, cdn.replace("%2Frelay%2F", "invalid"))


def test_rejects_wrong_endpoint_instead_of_misrouting_traffic() -> None:
    direct, cdn = links()
    with pytest.raises(ValueError):
        build_auto_route_config(direct.replace("reality", "tls"), cdn)
    with pytest.raises(ValueError):
        build_auto_route_config(direct, cdn.replace("xhttp", "ws"))


def test_network_display_labels_do_not_change_route_policy() -> None:
    direct, cdn = links()
    entries = build_network_display_configs(direct, cdn)
    assert len(entries) == 2
    assert "Wi-Fi only WiFi" in entries[0]["remarks"]
    assert "Mobile only Mobile" in entries[1]["remarks"]
    assert entries[0]["remarks"].startswith("🇳🇱")
    assert entries[1]["remarks"].startswith("🇳🇱")
    for entry in entries:
        assert entry["observatory"]["subjectSelector"] == ["vpn-direct"]
        assert entry["routing"]["balancers"][0]["fallbackTag"] == "vpn-cdn"
    assert entries[0]["outbounds"] == entries[1]["outbounds"]
    entries[0]["outbounds"][0]["tag"] = "mutated"
    assert entries[1]["outbounds"][0]["tag"] == "vpn-direct"
