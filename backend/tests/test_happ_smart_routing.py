import base64
import json

from app.services.happ_smart_routing import (
    HAPP_SMART_ROUTING_PROFILE,
    HAPP_SMART_ROUTING_VERSION,
    build_happ_smart_routing_link,
)


def decode_routing_link(link: str) -> dict:
    prefix = "happ://routing/onadd/"

    assert link.startswith(prefix)

    encoded = link.removeprefix(prefix)

    return json.loads(
        base64.b64decode(encoded).decode("utf-8")
    )


def test_smart_routing_link_contains_versioned_profile() -> None:
    profile = decode_routing_link(
        build_happ_smart_routing_link()
    )

    assert profile == HAPP_SMART_ROUTING_PROFILE
    assert profile["Name"] == "Work&PlayVPN Smart Routing"
    assert profile["GlobalProxy"] == "true"
    assert profile["LastUpdated"] == str(
        HAPP_SMART_ROUTING_VERSION
    )


def test_smart_routing_sends_russian_traffic_direct() -> None:
    profile = decode_routing_link(
        build_happ_smart_routing_link()
    )

    assert "geosite:category-ru" in profile["DirectSites"]
    assert "geoip:ru" in profile["DirectIp"]
    assert "geoip:private" in profile["DirectIp"]
    assert profile["ProxySites"] == []
    assert profile["ProxyIp"] == []


def test_smart_routing_uses_https_geodata_sources() -> None:
    profile = decode_routing_link(
        build_happ_smart_routing_link()
    )

    assert profile["Geoipurl"].startswith("https://")
    assert profile["Geositeurl"].startswith("https://")

