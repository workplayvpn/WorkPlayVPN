from app.services.subscription_client_diagnostics import (
    build_subscription_client_diagnostics,
)


def test_diagnostics_collects_client_metadata() -> None:
    diagnostics = build_subscription_client_diagnostics(
        {
            "User-Agent": "Happ/5.8.0/ios/example",
            "Sec-CH-UA-Model": '"iPhone 17 Pro Max"',
            "X-Device-OS": "iOS 26.0",
            "X-Client-Version": "5.8.0",
        }
    )

    assert diagnostics["metadata"] == {
        "user-agent": "Happ/5.8.0/ios/example",
        "sec-ch-ua-model": '"iPhone 17 Pro Max"',
        "x-device-os": "iOS 26.0",
        "x-client-version": "5.8.0",
    }


def test_diagnostics_never_exposes_secrets() -> None:
    diagnostics = build_subscription_client_diagnostics(
        {
            "Authorization": "Bearer secret-value",
            "Cookie": "session=secret-value",
            "X-Subscription-Token": "secret-value",
            "X-Telegram-Init-Data": "secret-value",
            "X-Device-Model": "iPhone 17 Pro Max",
        }
    )

    serialized = repr(diagnostics)

    assert "secret-value" not in serialized
    assert "authorization" not in diagnostics["header_names"]
    assert "cookie" not in diagnostics["header_names"]
    assert "x-subscription-token" not in diagnostics["header_names"]
    assert "x-telegram-init-data" not in diagnostics["header_names"]
    assert diagnostics["metadata"] == {
        "x-device-model": "iPhone 17 Pro Max",
    }


def test_diagnostics_hashes_device_identifiers() -> None:
    diagnostics = build_subscription_client_diagnostics(
        {
            "X-HWID": "private-device-identifier",
            "X-Device-ID": "another-private-identifier",
        }
    )

    serialized = repr(diagnostics)

    assert "private-device-identifier" not in serialized
    assert "another-private-identifier" not in serialized
    assert diagnostics["identifier_hashes"] == {
        "x-hwid": "223d7a92e925df26",
        "x-device-id": "4e48dbdb699ba85d",
    }
