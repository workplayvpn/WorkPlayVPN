from urllib.parse import parse_qs, unquote, urlsplit

from app.services.happ_network_candidates import network_candidates


DIRECT_UUID = "11111111-2222-4333-8444-555555555555"
MOBILE_UUID = "22222222-3333-4444-8555-666666666666"


def _links() -> list[str]:
    return [
        f"vless://{DIRECT_UUID}@nl.example:443?security=reality#"
        "%D0%9D%D0%B8%D0%B4%D0%B5%D1%80%D0%BB%D0%B0%D0%BD%D0%B4%D1%8B%20%E2%80%94%20Wi-Fi",
        f"vless://{MOBILE_UUID}@cdn.example:443?security=tls&type=xhttp#"
        "%D0%9D%D0%B8%D0%B4%D0%B5%D1%80%D0%BB%D0%B0%D0%BD%D0%B4%D1%8B%20%E2%80%94%20Mobile",
    ]


def test_network_candidates_keep_direct_primary_on_both_networks() -> None:
    result = network_candidates(
        _links(), direct_uuid=DIRECT_UUID, mobile_uuid=MOBILE_UUID,
    )
    assert [unquote(urlsplit(link).fragment) for link in result] == [
        "Нидерланды — Wi-Fi only WiFi",
        "Нидерланды — Direct only Mobile",
        "Нидерланды — Mobile only Mobile",
    ]
    assert [urlsplit(link).username for link in result] == [
        DIRECT_UUID, DIRECT_UUID, MOBILE_UUID,
    ]
    assert [parse_qs(urlsplit(link).query)["security"][0] for link in result] == [
        "reality", "reality", "tls",
    ]
    assert [urlsplit(link).hostname for link in result] == [
        "nl.example", "nl.example", "cdn.example",
    ]


def test_missing_mobile_route_does_not_hide_direct_on_cellular() -> None:
    links = _links()[:1]
    assert network_candidates(
        links, direct_uuid=DIRECT_UUID, mobile_uuid=MOBILE_UUID,
    ) == links


def test_credentials_mismatch_leaves_existing_feed_untouched() -> None:
    links = _links()
    assert network_candidates(
        links, direct_uuid=DIRECT_UUID, mobile_uuid=DIRECT_UUID,
    ) == links
    assert network_candidates(
        links, direct_uuid="wrong", mobile_uuid=MOBILE_UUID,
    ) == links
