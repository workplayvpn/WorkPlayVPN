import json
from decimal import Decimal
from urllib.error import URLError
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.services.payment_providers.cloudpayments import (
    CloudPaymentsProvider,
)


def test_cloudpayments_provider_success() -> None:
    provider = CloudPaymentsProvider()

    response = MagicMock()
    response.__enter__.return_value = response
    response.__exit__.return_value = False
    response.read.return_value = (
        b'{"Success":true,'
        b'"Model":{'
        b'"Id":"cp_order_test_123",'
        b'"Url":"https://orders.cloudpayments.ru/test/123"'
        b'}}'
    )

    with patch(
        "app.services.payment_providers.cloudpayments.urlopen",
        return_value=response,
    ):
        with patch(
            "app.services.payment_providers.cloudpayments."
            "settings.cloudpayments_public_id",
            "pk_test",
        ):
            with patch(
                "app.services.payment_providers.cloudpayments."
                "settings.cloudpayments_api_secret",
                "secret_test",
            ):
                result = provider.create_payment(
                    amount=Decimal("199.00"),
                    currency="RUB",
                    description="Work&PlayVPN test",
                    idempotency_key="cp-local-test-001",
                    metadata={
                        "payment_id": "123",
                        "user_id": "4",
                    },
                )

    assert result.provider_payment_id == "cp_order_test_123"
    assert (
        result.confirmation_url
        == "https://orders.cloudpayments.ru/test/123"
    )


def test_cloudpayments_provider_success_false() -> None:
    provider = CloudPaymentsProvider()

    response = MagicMock()
    response.__enter__.return_value = response
    response.__exit__.return_value = False
    response.read.return_value = (
        b'{"Success":false,"Message":"Rejected"}'
    )

    with patch(
        "app.services.payment_providers.cloudpayments.urlopen",
        return_value=response,
    ):
        with patch(
            "app.services.payment_providers.cloudpayments."
            "settings.cloudpayments_public_id",
            "pk_test",
        ):
            with patch(
                "app.services.payment_providers.cloudpayments."
                "settings.cloudpayments_api_secret",
                "secret_test",
            ):
                with pytest.raises(HTTPException) as exc_info:
                    provider.create_payment(
                        amount=Decimal("199.00"),
                        currency="RUB",
                        description="Work&PlayVPN test",
                        idempotency_key="cp-local-test-002",
                        metadata={
                            "payment_id": "124",
                            "user_id": "4",
                        },
                    )

    assert exc_info.value.status_code == 502
    assert (
        exc_info.value.detail
        == "CloudPayments payment creation failed"
    )


def test_cloudpayments_provider_network_error() -> None:
    provider = CloudPaymentsProvider()

    with patch(
        "app.services.payment_providers.cloudpayments.urlopen",
        side_effect=URLError("network unavailable"),
    ):
        with patch(
            "app.services.payment_providers.cloudpayments."
            "settings.cloudpayments_public_id",
            "pk_test",
        ):
            with patch(
                "app.services.payment_providers.cloudpayments."
                "settings.cloudpayments_api_secret",
                "secret_test",
            ):
                with pytest.raises(HTTPException) as exc_info:
                    provider.create_payment(
                        amount=Decimal("199.00"),
                        currency="RUB",
                        description="Work&PlayVPN test",
                        idempotency_key="cp-local-test-003",
                        metadata={
                            "payment_id": "125",
                            "user_id": "4",
                        },
                    )

    assert exc_info.value.status_code == 502
    assert (
        exc_info.value.detail
        == "CloudPayments unavailable"
    )


def test_cloudpayments_provider_cancel_success() -> None:
    provider = CloudPaymentsProvider()

    response = MagicMock()
    response.__enter__.return_value = response
    response.__exit__.return_value = False
    response.read.return_value = (
        b'{"Success":true,"Message":null}'
    )

    with patch(
        "app.services.payment_providers.cloudpayments.urlopen",
        return_value=response,
    ) as urlopen_mock:
        with patch(
            "app.services.payment_providers.cloudpayments."
            "settings.cloudpayments_public_id",
            "pk_test",
        ):
            with patch(
                "app.services.payment_providers.cloudpayments."
                "settings.cloudpayments_api_secret",
                "secret_test",
            ):
                provider.cancel_payment(
                    provider_payment_id="cp_order_test_123",
                )

    urlopen_mock.assert_called_once()

    request = urlopen_mock.call_args.args[0]

    assert (
        request.full_url
        == "https://api.cloudpayments.ru/orders/cancel"
    )
    assert request.get_method() == "POST"
    assert json.loads(request.data.decode("utf-8")) == {
        "Id": "cp_order_test_123",
    }


def test_cloudpayments_provider_cancel_success_false() -> None:
    provider = CloudPaymentsProvider()

    response = MagicMock()
    response.__enter__.return_value = response
    response.__exit__.return_value = False
    response.read.return_value = (
        b'{"Success":false,"Message":"Rejected"}'
    )

    with patch(
        "app.services.payment_providers.cloudpayments.urlopen",
        return_value=response,
    ):
        with patch(
            "app.services.payment_providers.cloudpayments."
            "settings.cloudpayments_public_id",
            "pk_test",
        ):
            with patch(
                "app.services.payment_providers.cloudpayments."
                "settings.cloudpayments_api_secret",
                "secret_test",
            ):
                with pytest.raises(
                    HTTPException
                ) as exc_info:
                    provider.cancel_payment(
                        provider_payment_id=(
                            "cp_order_test_124"
                        ),
                    )

    assert exc_info.value.status_code == 502
    assert (
        exc_info.value.detail
        == "CloudPayments payment cancellation failed"
    )


def test_cloudpayments_provider_cancel_network_error() -> None:
    provider = CloudPaymentsProvider()

    with patch(
        "app.services.payment_providers.cloudpayments.urlopen",
        side_effect=URLError("network unavailable"),
    ):
        with patch(
            "app.services.payment_providers.cloudpayments."
            "settings.cloudpayments_public_id",
            "pk_test",
        ):
            with patch(
                "app.services.payment_providers.cloudpayments."
                "settings.cloudpayments_api_secret",
                "secret_test",
            ):
                with pytest.raises(
                    HTTPException
                ) as exc_info:
                    provider.cancel_payment(
                        provider_payment_id=(
                            "cp_order_test_125"
                        ),
                    )

    assert exc_info.value.status_code == 502
    assert (
        exc_info.value.detail
        == "CloudPayments unavailable"
    )