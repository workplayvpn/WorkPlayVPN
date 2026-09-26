import json
from urllib.parse import parse_qs, unquote, urlsplit

from app.models.vpn_device import VpnDevice
from app.models.vpn_node import VpnNode
from app.models.vpn_node_profile import VpnNodeProfile
from app.services.client_profiles.happ import HappProfile


DEVICE_UUID = "11111111-2222-4333-8444-555555555555"


def build_device() -> VpnDevice:
    return VpnDevice(
        id=7,
        user_id=1,
        node_id=1,
        device_name="iPhone",
        xray_uuid=DEVICE_UUID,
        xray_email="device-7@workplayvpn",
        is_active=True,
    )


def build_node() -> VpnNode:
    return VpnNode(
        id=1,
        location_id=1,
        code="nl-01",
        name="WorkPlayVPN-NL-01",
        host="nl1.workplayvpn.ru",
        ssh_user="workplayvpn",
        is_active=True,
    )


def build_profile(
    *,
    profile_id: int,
    code: str,
    network: str,
    security: str,
    port: int,
    settings: dict,
) -> VpnNodeProfile:
    return VpnNodeProfile(
        id=profile_id,
        node_id=1,
        code=code,
        name=code,
        protocol="vless",
        network=network,
        security=security,
        port=port,
        flow=None,
        server_name="edge.workplayvpn.ru",
        settings=settings,
        is_active=True,
    )


def test_legacy_happ_profile_output_remains_unchanged() -> None:
    profile = build_profile(
        profile_id=1,
        code="nl-01-vless-xhttp",
        network="xhttp",
        security="tls",
        port=8443,
        settings={
            "fingerprint": "chrome",
            "path": "/m/abc",
            "mode": "auto",
        },
    )

    links = HappProfile().build_links(
        device=build_device(),
        nodes=[build_node()],
        profiles=[profile],
    )

    assert len(links) == 1
    assert "@nl1.workplayvpn.ru:8443" in links[0]
    assert links[0].endswith("#WorkPlayVPN-NL-01")


def test_mobile_profile_is_hidden_without_rollout() -> None:
    wifi_profile = build_profile(
        profile_id=1,
        code="nl-01-happ-wifi",
        network="xhttp",
        security="tls",
        port=8443,
        settings={
            "happ_access_mode": "wifi",
            "path": "/wifi",
        },
    )
    mobile_profile = build_profile(
        profile_id=2,
        code="nl-01-happ-mobile",
        network="xhttp",
        security="tls",
        port=443,
        settings={
            "happ_access_mode": "mobile",
            "happ_server_address": "mobile.workplayvpn.ru",
            "path": "/mobile",
        },
    )

    links = HappProfile().build_links(
        device=build_device(),
        nodes=[build_node()],
        profiles=[wifi_profile, mobile_profile],
        include_happ_mobile=False,
    )

    assert len(links) == 1
    assert "@nl1.workplayvpn.ru:8443" in links[0]
    assert unquote(urlsplit(links[0]).fragment) == "WorkPlayVPN-NL-01"


def test_basic_happ_prefers_direct_reality_and_hides_mobile() -> None:
    legacy = build_profile(
        profile_id=1,
        code="nl-01-vless-xhttp",
        network="xhttp",
        security="tls",
        port=8443,
        settings={"path": "/legacy"},
    )
    direct = build_profile(
        profile_id=2,
        code="nl-01-reality",
        network="tcp",
        security="reality",
        port=443,
        settings={"public_key": "test-key"},
    )
    mobile = build_profile(
        profile_id=3,
        code="nl-01-mobile",
        network="xhttp",
        security="tls",
        port=443,
        settings={
            "happ_access_mode": "mobile",
            "happ_server_address": "cdn.bot-forma.ru",
            "path": "/wp-bf/",
        },
    )

    links = HappProfile().build_links(
        device=build_device(),
        nodes=[build_node()],
        profiles=[legacy, direct, mobile],
    )

    assert len(links) == 1
    assert "@nl1.workplayvpn.ru:443" in links[0]
    assert parse_qs(urlsplit(links[0]).query)["security"] == ["reality"]
    assert unquote(urlsplit(links[0]).fragment) == "WorkPlayVPN-NL-01"


def test_basic_happ_uses_the_same_country_label_as_mobile_wifi() -> None:
    direct = build_profile(
        profile_id=2,
        code="nl-01-reality",
        network="tcp",
        security="reality",
        port=443,
        settings={
            "happ_display_name": "Нидерланды — Wi-Fi",
            "public_key": "test-key",
        },
    )
    mobile = build_profile(
        profile_id=3,
        code="nl-01-mobile",
        network="xhttp",
        security="tls",
        port=443,
        settings={
            "happ_access_mode": "mobile",
            "happ_server_address": "cdn.bot-forma.ru",
            "happ_display_name": "Нидерланды — Mobile",
            "path": "/wp-bf/",
        },
    )

    basic_links = HappProfile().build_links(
        device=build_device(), nodes=[build_node()], profiles=[direct, mobile],
    )
    mobile_links = HappProfile().build_links(
        device=build_device(), nodes=[build_node()], profiles=[direct, mobile],
        include_happ_mobile=True,
    )

    assert [unquote(urlsplit(link).fragment) for link in basic_links] == [
        "Нидерланды",
    ]
    assert [unquote(urlsplit(link).fragment) for link in mobile_links] == [
        "Нидерланды — Wi-Fi", "Нидерланды — Mobile",
    ]
    assert urlsplit(basic_links[0]).username == urlsplit(mobile_links[0]).username


def test_wifi_and_mobile_links_share_one_device_uuid() -> None:
    wifi_profile = build_profile(
        profile_id=1,
        code="nl-01-happ-wifi",
        network="xhttp",
        security="tls",
        port=8443,
        settings={
            "happ_access_mode": "wifi",
            "happ_display_name": "Netherlands — Wi-Fi",
            "path": "/wifi",
        },
    )
    mobile_profile = build_profile(
        profile_id=2,
        code="nl-01-happ-mobile",
        network="xhttp",
        security="tls",
        port=443,
        settings={
            "happ_access_mode": "mobile",
            "happ_server_address": "mobile.workplayvpn.ru",
            "happ_display_name": "Netherlands — Mobile",
            "fingerprint": "chrome",
            "path": "/mobile/opaque",
            "mode": "auto",
            "alpn": ["h2"],
        },
    )

    links = HappProfile().build_links(
        device=build_device(),
        nodes=[build_node()],
        profiles=[wifi_profile, mobile_profile],
        include_happ_mobile=True,
    )

    assert len(links) == 2

    parsed_links = [
        urlsplit(link)
        for link in links
    ]

    assert [link.username for link in parsed_links] == [
        DEVICE_UUID,
        DEVICE_UUID,
    ]
    assert [link.hostname for link in parsed_links] == [
        "nl1.workplayvpn.ru",
        "mobile.workplayvpn.ru",
    ]
    assert [unquote(link.fragment) for link in parsed_links] == [
        "Netherlands — Wi-Fi",
        "Netherlands — Mobile",
    ]

    mobile_query = parse_qs(parsed_links[1].query)

    assert mobile_query["type"] == ["xhttp"]
    assert mobile_query["security"] == ["tls"]
    assert mobile_query["path"] == ["/mobile/opaque"]
    assert mobile_query["mode"] == ["auto"]
    assert mobile_query["alpn"] == ["h2"]


def test_paid_mobile_link_uses_separate_device_uuid() -> None:
    device = build_device()
    device.mobile_xray_uuid = "22222222-3333-4444-8555-666666666666"
    device.mobile_xray_email = "mobile_" + "a" * 32 + "@workplayvpn"
    direct = build_profile(
        profile_id=1, code="direct", network="tcp", security="reality",
        port=443, settings={},
    )
    mobile = build_profile(
        profile_id=2, code="mobile", network="xhttp", security="tls",
        port=443, settings={
            "happ_access_mode": "mobile",
            "happ_server_address": "cdn.bot-forma.ru",
            "path": "/wp-bf/",
            "mode": "packet-up",
            "alpn": "h2",
            "host": "cdn.bot-forma.ru",
            "xhttp_extra": {
                "uplinkHTTPMethod": "GET",
                "uplinkDataPlacement": "body",
            },
        },
    )
    links = HappProfile().build_links(
        device=device, nodes=[build_node()],
        profiles=[direct, mobile], include_happ_mobile=True,
    )
    assert len(links) == 2
    assert urlsplit(links[0]).username == DEVICE_UUID
    assert urlsplit(links[1]).username == device.mobile_xray_uuid
    assert parse_qs(urlsplit(links[1]).query)["alpn"] == ["h2"]
    assert parse_qs(urlsplit(links[1]).query)["host"] == ["cdn.bot-forma.ru"]
    assert json.loads(parse_qs(urlsplit(links[1]).query)["extra"][0]) == {
        "uplinkHTTPMethod": "GET",
        "uplinkDataPlacement": "body",
    }
    assert "extra" not in parse_qs(urlsplit(links[0]).query)


def test_mobile_role_does_not_replace_legacy_wifi_fallback() -> None:
    legacy_profile = build_profile(
        profile_id=1,
        code="nl-01-vless-xhttp",
        network="xhttp",
        security="tls",
        port=8443,
        settings={"path": "/legacy"},
    )
    mobile_profile = build_profile(
        profile_id=2,
        code="nl-01-happ-mobile",
        network="xhttp",
        security="tls",
        port=443,
        settings={
            "happ_access_mode": "mobile",
            "happ_server_address": "mobile.workplayvpn.ru",
            "path": "/mobile",
        },
    )

    links = HappProfile().build_links(
        device=build_device(),
        nodes=[build_node()],
        profiles=[legacy_profile, mobile_profile],
        include_happ_mobile=True,
    )

    assert len(links) == 2
    assert "@nl1.workplayvpn.ru:8443" in links[0]
    assert "@mobile.workplayvpn.ru:443" in links[1]


def test_mobile_profile_is_hidden_without_dedicated_server_address() -> None:
    wifi_profile = build_profile(
        profile_id=1,
        code="nl-01-happ-wifi",
        network="xhttp",
        security="tls",
        port=8443,
        settings={
            "happ_access_mode": "wifi",
            "path": "/wifi",
        },
    )
    mobile_profile = build_profile(
        profile_id=2,
        code="nl-01-happ-mobile",
        network="xhttp",
        security="tls",
        port=443,
        settings={
            "happ_access_mode": "mobile",
            "path": "/mobile",
        },
    )

    links = HappProfile().build_links(
        device=build_device(),
        nodes=[build_node()],
        profiles=[wifi_profile, mobile_profile],
        include_happ_mobile=True,
    )

    assert len(links) == 1
    assert "@nl1.workplayvpn.ru:8443" in links[0]


def test_mobile_profile_is_hidden_without_tls() -> None:
    wifi_profile = build_profile(
        profile_id=1,
        code="nl-01-happ-wifi",
        network="xhttp",
        security="tls",
        port=8443,
        settings={
            "happ_access_mode": "wifi",
            "path": "/wifi",
        },
    )
    mobile_profile = build_profile(
        profile_id=2,
        code="nl-01-happ-mobile",
        network="xhttp",
        security="none",
        port=443,
        settings={
            "happ_access_mode": "mobile",
            "happ_server_address": "mobile.workplayvpn.ru",
            "path": "/mobile",
        },
    )

    links = HappProfile().build_links(
        device=build_device(),
        nodes=[build_node()],
        profiles=[wifi_profile, mobile_profile],
        include_happ_mobile=True,
    )

    assert len(links) == 1
    assert "@nl1.workplayvpn.ru:8443" in links[0]


def test_mobile_profile_is_hidden_for_unsupported_transport() -> None:
    wifi_profile = build_profile(
        profile_id=1,
        code="nl-01-happ-wifi",
        network="xhttp",
        security="tls",
        port=8443,
        settings={
            "happ_access_mode": "wifi",
            "path": "/wifi",
        },
    )
    mobile_profile = build_profile(
        profile_id=2,
        code="nl-01-happ-mobile",
        network="tcp",
        security="tls",
        port=443,
        settings={
            "happ_access_mode": "mobile",
            "happ_server_address": "mobile.workplayvpn.ru",
        },
    )

    links = HappProfile().build_links(
        device=build_device(),
        nodes=[build_node()],
        profiles=[wifi_profile, mobile_profile],
        include_happ_mobile=True,
    )

    assert len(links) == 1
    assert "@nl1.workplayvpn.ru:8443" in links[0]


def test_mobile_xhttp_profile_is_hidden_without_path() -> None:
    wifi_profile = build_profile(
        profile_id=1,
        code="nl-01-happ-wifi",
        network="xhttp",
        security="tls",
        port=8443,
        settings={
            "happ_access_mode": "wifi",
            "path": "/wifi",
        },
    )
    mobile_profile = build_profile(
        profile_id=2,
        code="nl-01-happ-mobile",
        network="xhttp",
        security="tls",
        port=443,
        settings={
            "happ_access_mode": "mobile",
            "happ_server_address": "mobile.workplayvpn.ru",
        },
    )

    links = HappProfile().build_links(
        device=build_device(),
        nodes=[build_node()],
        profiles=[wifi_profile, mobile_profile],
        include_happ_mobile=True,
    )

    assert len(links) == 1
    assert "@nl1.workplayvpn.ru:8443" in links[0]


def test_mobile_profile_is_hidden_for_invalid_server_address() -> None:
    invalid_addresses = (
        "https://mobile.workplayvpn.ru",
        "mobile.workplayvpn.ru/path",
        "mobile workplayvpn.ru",
    )

    for server_address in invalid_addresses:
        mobile_profile = build_profile(
            profile_id=2,
            code="nl-01-happ-mobile",
            network="xhttp",
            security="tls",
            port=443,
            settings={
                "happ_access_mode": "mobile",
                "happ_server_address": server_address,
                "path": "/mobile",
            },
        )

        assert not HappProfile._is_mobile_profile_ready(
            mobile_profile
        )


def test_mobile_profile_is_hidden_for_invalid_port() -> None:
    for port in (0, 65536):
        mobile_profile = build_profile(
            profile_id=2,
            code="nl-01-happ-mobile",
            network="xhttp",
            security="tls",
            port=port,
            settings={
                "happ_access_mode": "mobile",
                "happ_server_address": "mobile.workplayvpn.ru",
                "path": "/mobile",
            },
        )

        assert not HappProfile._is_mobile_profile_ready(
            mobile_profile
        )
