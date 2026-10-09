import hashlib
import json
from decimal import Decimal
from unittest.mock import patch
from urllib.parse import parse_qs, unquote, urlparse

import pytest
from fastapi import HTTPException

from app.services.payment_providers.robokassa import (
    RobokassaProvider,
)


def test_robokassa_provider_creates_signed_test_url() -> None:
    provider = RobokassaProvider()

    with (
        patch(
            "app.services.payment_providers.robokassa."
            "settings.robokassa_merchant_login",
            "workplayvpn",
        ),
        patch(
            "app.services.payment_providers.robokassa."
            "settings.robokassa_password_1",
            "test-password-1",
        ),
        patch(
            "app.services.payment_providers.robokassa."
            "settings.robokassa_hash_algorithm",
            "sha256",
        ),
        patch(
            "app.services.payment_providers.robokassa."
            "settings.robokassa_is_test",
            True,
        ),
        patch(
            "app.services.payment_providers.robokassa."
            "settings.payment_mode",
            "test",
        ),
    ):
        result = provider.create_payment(
            amount=Decimal("199.00"),
            currency="RUB",
            description="WorkPlayVPN 1 month",
            idempotency_key="rk-test-001",
            metadata={
                "payment_id": "123",
                "expires_at": (
                    "2026-09-12T12:34:56+00:00"
                ),
            },
        )

    query = parse_qs(
        urlparse(result.confirmation_url).query
    )

    expected_signature = hashlib.sha256(
        f"workplayvpn:199.00:123:{query['Receipt'][0]}:test-password-1".encode()
    ).hexdigest()

    receipt = json.loads(unquote(query["Receipt"][0]))
    assert receipt == {"items": [{"name": "WorkPlayVPN 1 month", "quantity": 1, "sum": 199.0, "tax": "none"}]}
    assert result.provider_payment_id == "robokassa:123"
    assert query["MerchantLogin"] == ["workplayvpn"]
    assert query["OutSum"] == ["199.00"]
    assert query["InvId"] == ["123"]
    assert query["SignatureValue"] == [
        expected_signature
    ]
    assert query["IsTest"] == ["1"]
    assert query["ExpirationDate"] == [
        "2026-09-12T15:34"
    ]


def test_robokassa_provider_requires_credentials() -> None:
    provider = RobokassaProvider()

    with (
        patch(
            "app.services.payment_providers.robokassa."
            "settings.robokassa_merchant_login",
            None,
        ),
        patch(
            "app.services.payment_providers.robokassa."
            "settings.robokassa_password_1",
            None,
        ),
    ):
        with pytest.raises(HTTPException) as exc_info:
            provider.create_payment(
                amount=Decimal("199.00"),
                currency="RUB",
                description="WorkPlayVPN test",
                idempotency_key="rk-test-002",
                metadata={"payment_id": "124"},
            )

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == (
        "Robokassa is not configured"
    )


def test_robokassa_provider_rejects_mode_mismatch() -> None:
    provider = RobokassaProvider()

    with (
        patch(
            "app.services.payment_providers.robokassa."
            "settings.robokassa_merchant_login",
            "workplayvpn",
        ),
        patch(
            "app.services.payment_providers.robokassa."
            "settings.robokassa_password_1",
            "test-password-1",
        ),
        patch(
            "app.services.payment_providers.robokassa."
            "settings.robokassa_is_test",
            False,
        ),
        patch(
            "app.services.payment_providers.robokassa."
            "settings.payment_mode",
            "test",
        ),
    ):
        with pytest.raises(HTTPException) as exc_info:
            provider.create_payment(
                amount=Decimal("199.00"),
                currency="RUB",
                description="WorkPlayVPN test",
                idempotency_key="rk-test-003",
                metadata={"payment_id": "125"},
            )

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == (
        "Robokassa payment mode is inconsistent"
    )


def test_robokassa_provider_rejects_non_rub() -> None:
    provider = RobokassaProvider()

    with (
        patch(
            "app.services.payment_providers.robokassa."
            "settings.robokassa_merchant_login",
            "workplayvpn",
        ),
        patch(
            "app.services.payment_providers.robokassa."
            "settings.robokassa_password_1",
            "test-password-1",
        ),
        patch(
            "app.services.payment_providers.robokassa."
            "settings.robokassa_is_test",
            True,
        ),
        patch(
            "app.services.payment_providers.robokassa."
            "settings.payment_mode",
            "test",
        ),
    ):
        with pytest.raises(HTTPException) as exc_info:
            provider.create_payment(
                amount=Decimal("1.00"),
                currency="USD",
                description="WorkPlayVPN test",
                idempotency_key="rk-test-004",
                metadata={"payment_id": "126"},
            )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == (
        "Robokassa supports RUB payments only"
    )
