import base64
from datetime import UTC, datetime, timedelta, timezone

import pytest

from app.api.subscription_feed import (
    HAPP_SUBSCRIPTION_HEADERS,
    build_subscription_payload,
    build_subscription_response_headers,
    should_include_happ_mobile_profile,
    should_include_happ_smart_routing,
)
from app.services.happ_subscription_info import (
    subscription_expiry_info, subscription_presentation,
)


def test_basic_and_mobile_have_distinct_happ_descriptions() -> None:
    basic = subscription_presentation(access_tier="basic")
    mobile = subscription_presentation(access_tier="mobile", routed_mobile=True)
    assert basic["profile-title"] == "Work&PlayVPN Basic"
    assert mobile["profile-title"] == "Work&PlayVPN Mobile"
    assert all(len(item["profile-title"]) <= 25 for item in (basic, mobile))
    def description(item):
        return base64.b64decode(item["announce"].removeprefix("base64:")).decode("utf-8")
    assert "Нидерландах" in description(basic)
    assert "автоматически" in description(mobile)
    assert description(basic) != description(mobile)


def test_happ_expiry_only_metadata_tracks_the_actual_instant() -> None:
    expires_at = datetime(2026, 10, 27, 13, 15, tzinfo=UTC)
    in_moscow = expires_at.astimezone(timezone(timedelta(hours=3)))
    expected = f"expire={int(expires_at.timestamp())}"
    assert subscription_expiry_info(in_moscow) == expected

    payload = build_subscription_payload(
        client="happ", links=["vless://device"], expires_at=in_moscow,
    )
    headers = build_subscription_response_headers(
        client="happ", expires_at=in_moscow,
    )
    assert f"#subscription-userinfo: {expected}" in payload.splitlines()
    assert headers["subscription-userinfo"] == expected
    assert "upload=" not in payload and "download=" not in payload
    assert "total=" not in payload


def test_happ_expiry_is_omitted_when_unknown_or_client_is_not_happ() -> None:
    expires_at = datetime(2026, 10, 27, tzinfo=UTC)
    assert subscription_expiry_info(None) is None
    assert "subscription-userinfo" not in build_subscription_response_headers(
        client="happ",
    )
    assert "subscription-userinfo" not in build_subscription_response_headers(
        client="generic", expires_at=expires_at,
    )
    assert "subscription-userinfo" not in build_subscription_payload(
        client="generic", links=["vless://device"], expires_at=expires_at,
    )
    with pytest.raises(ValueError, match="timezone"):
        subscription_expiry_info(datetime(2026, 10, 27))


def test_happ_subscription_payload_contains_metadata() -> None:
    link = (
        "vless://device@example.com:8443"
        "?type=xhttp&security=tls#WorkPlayVPN-NL-01"
    )

    payload = build_subscription_payload(
        client="happ",
        links=[link],
    )

    lines = payload.splitlines()

    for name, value in HAPP_SUBSCRIPTION_HEADERS.items():
        assert f"#{name}: {value}" in lines

    assert lines[-1] == link
    assert "type=xhttp" in lines[-1]
    assert "security=tls" in lines[-1]

    encoded = base64.b64encode(
        payload.encode("utf-8")
    ).decode("ascii")

    assert (
        base64.b64decode(encoded).decode("utf-8")
        == payload
    )


def test_non_happ_payload_remains_unchanged() -> None:
    links = [
        "vless://first@example.com:443",
        "vless://second@example.com:443",
    ]

    payload = build_subscription_payload(
        client="generic",
        links=links,
    )

    assert payload == "\n".join(links)
    assert "#profile-title" not in payload


def test_mobile_happ_metadata_uses_full_brand() -> None:
    payload = build_subscription_payload(
        client="happ", links=["vless://example"], access_tier="mobile",
    )
    headers = build_subscription_response_headers(
        client="happ", access_tier="mobile",
    )
    assert "#profile-title: Work&PlayVPN Mobile" in payload.splitlines()
    assert headers["profile-title"] == "Work&PlayVPN Mobile"


def test_happ_response_headers_can_include_routing() -> None:
    routing_link = "happ://routing/onadd/example"

    headers = build_subscription_response_headers(
        client="happ",
        routing_link=routing_link,
    )

    assert headers["routing"] == routing_link
    assert headers["profile-title"] == "Work&PlayVPN Basic"


def test_non_happ_response_headers_ignore_routing() -> None:
    headers = build_subscription_response_headers(
        client="generic",
        routing_link="happ://routing/onadd/example",
    )

    assert "routing" not in headers
    assert "profile-title" not in headers
    assert headers["Cache-Control"] == "no-store"


def test_happ_mobile_profile_rollout_is_closed_by_default() -> None:
    assert not should_include_happ_mobile_profile(
        client="happ",
        user_id=1,
        configured_user_ids="",
    )


def test_happ_mobile_profile_rollout_supports_canary_users() -> None:
    assert should_include_happ_mobile_profile(
        client="happ",
        user_id=33,
        configured_user_ids="1, 33,49",
    )
    assert not should_include_happ_mobile_profile(
        client="happ",
        user_id=63,
        configured_user_ids="1, 33,49",
    )


def test_happ_mobile_profile_rollout_supports_global_flag() -> None:
    assert should_include_happ_mobile_profile(
        client="happ",
        user_id=103,
        configured_user_ids="*",
    )
    assert not should_include_happ_mobile_profile(
        client="generic",
        user_id=103,
        configured_user_ids="*",
    )


def test_happ_smart_routing_rollout_is_closed_by_default() -> None:
    assert not should_include_happ_smart_routing(
        client="happ",
        user_id=1,
        configured_user_ids="",
    )


def test_happ_smart_routing_rollout_supports_canary_users() -> None:
    assert should_include_happ_smart_routing(
        client="happ",
        user_id=33,
        configured_user_ids="1, 33,49",
    )
    assert not should_include_happ_smart_routing(
        client="happ",
        user_id=63,
        configured_user_ids="1, 33,49",
    )


def test_happ_smart_routing_rollout_supports_global_flag() -> None:
    assert should_include_happ_smart_routing(
        client="happ",
        user_id=103,
        configured_user_ids="*",
    )
    assert not should_include_happ_smart_routing(
        client="generic",
        user_id=103,
        configured_user_ids="*",
    )
