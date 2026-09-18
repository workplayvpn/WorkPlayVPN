import base64

from app.api.subscription_feed import (
    HAPP_SUBSCRIPTION_HEADERS,
    build_subscription_payload,
)


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
