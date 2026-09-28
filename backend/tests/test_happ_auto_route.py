from urllib.parse import urlencode

import pytest

from app.services.happ_auto_route import (
    build_auto_route_config,
    build_routed_auto_config,
)
from app.services.happ_smart_routing import HAPP_SMART_ROUTING_PROFILE


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
    assert config["remarks"] == "Work&PlayVPN Mobile Auto — pilot"
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


def test_routed_canary_keeps_failover_and_bypasses_ru() -> None:
    direct, cdn = links()
    normal = build_auto_route_config(direct, cdn)[0]
    routed = build_routed_auto_config(direct, cdn)[0]
    assert routed["remarks"] == "🇳🇱 Нидерланды"
    assert routed["outbounds"][:2] == normal["outbounds"]
    assert routed["outbounds"][2]["tag"] == "ru-direct"
    assert routed["outbounds"][2]["streamSettings"]["sockopt"]["domainStrategy"] == "UseIP"
    assert "settings" not in routed["outbounds"][2]
    assert routed["routing"]["rules"][:2] == [
        {"type": "field", "domain": HAPP_SMART_ROUTING_PROFILE["DirectSites"],
         "outboundTag": "ru-direct"},
        {"type": "field", "ip": HAPP_SMART_ROUTING_PROFILE["DirectIp"],
         "outboundTag": "ru-direct"},
    ]
    assert routed["routing"]["rules"][2] == normal["routing"]["rules"][0]
    assert routed["routing"]["balancers"] == normal["routing"]["balancers"]
    assert routed["dns"]["servers"][0]["address"] == "77.88.8.8"
