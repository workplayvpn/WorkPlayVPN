import base64
import hashlib
import hmac
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from urllib.parse import unquote_plus

import pytest
from fastapi import HTTPException

from app.models.payment import Payment
from app.models.subscription import Subscription
from app.services.cloudpayments_webhook import (
    CloudPaymentsWebhookService,
)


TEST_SECRET = "test-cloudpayments-secret"


def make_payment(
    *,
    payment_id: int = 100,
    user_id: int = 4,
    subscription_id: int = 200,
    provider: str = "cloudpayments",
    status: str = "pending",
    amount: Decimal = Decimal("199.00"),
    currency: str = "RUB",
    provider_payment_id: str | None = None,
):
    return SimpleNamespace(
        id=payment_id,
        user_id=user_id,
        subscription_id=subscription_id,
        provider=provider,
        status=status,
        amount=amount,
        currency=currency,
        provider_payment_id=provider_payment_id,
    )


def make_subscription(
    *,
    subscription_id: int = 200,
):
    return SimpleNamespace(
        id=subscription_id,
    )


def make_database(
    payment,
    subscription,
):
    database = MagicMock()

    def get_side_effect(model, object_id):
        if model is Payment:
            if object_id == payment.id:
                return payment

        if model is Subscription:
            if object_id == subscription.id:
                return subscription

        return None

    database.get.side_effect = get_side_effect

    return database


def calculate_content_hmac(
    body: bytes,
) -> str:
    digest = hmac.new(
        TEST_SECRET.encode("utf-8"),
        body,
        hashlib.sha256,
    ).digest()

    return base64.b64encode(
        digest
    ).decode("ascii")


def calculate_x_content_hmac(
    body: bytes,
) -> str:
    decoded_body = unquote_plus(
        body.decode("utf-8")
    ).encode("utf-8")

    digest = hmac.new(
        TEST_SECRET.encode("utf-8"),
        decoded_body,
        hashlib.sha256,
    ).digest()

    return base64.b64encode(
        digest
    ).decode("ascii")


def test_valid_content_hmac() -> None:
    service = CloudPaymentsWebhookService()

    body = (
        b"InvoiceId=100"
        b"&TransactionId=cp-test-100"
        b"&Amount=199.00"
        b"&Currency=RUB"
        b"&AccountId=4"
    )

    signature = calculate_content_hmac(
        body
    )

    with patch(
        "app.services.cloudpayments_webhook."
        "settings.cloudpayments_api_secret",
        TEST_SECRET,
    ):
        service.verify_signature(
            raw_body=body,
            x_content_hmac=None,
            content_hmac=signature,
        )


def test_valid_x_content_hmac() -> None:
    service = CloudPaymentsWebhookService()

    body = (
        b"InvoiceId=100"
        b"&TransactionId=cp-test-100"
        b"&Amount=199.00"
        b"&Currency=RUB"
        b"&AccountId=4"
        b"&Description=Work%26PlayVPN+Test"
    )

    signature = calculate_x_content_hmac(
        body
    )

    with patch(
        "app.services.cloudpayments_webhook."
        "settings.cloudpayments_api_secret",
        TEST_SECRET,
    ):
        service.verify_signature(
            raw_body=body,
            x_content_hmac=signature,
            content_hmac=None,
        )


def test_invalid_signature_is_rejected() -> None:
    service = CloudPaymentsWebhookService()

    body = (
        b"InvoiceId=100"
        b"&TransactionId=cp-test-100"
        b"&Amount=199.00"
        b"&Currency=RUB"
        b"&AccountId=4"
    )

    with patch(
        "app.services.cloudpayments_webhook."
        "settings.cloudpayments_api_secret",
        TEST_SECRET,
    ):
        with pytest.raises(
            HTTPException
        ) as exc_info:
            service.verify_signature(
                raw_body=body,
                x_content_hmac=None,
                content_hmac="invalid-signature",
            )

    assert exc_info.value.status_code == 401
    assert (
        exc_info.value.detail
        == "Invalid CloudPayments signature"
    )


def test_amount_mismatch_is_rejected() -> None:
    service = CloudPaymentsWebhookService()

    payment = make_payment()
    subscription = make_subscription()
    database = make_database(
        payment,
        subscription,
    )

    payload = {
        "InvoiceId": "100",
        "TransactionId": "cp-test-100",
        "Amount": "198.00",
        "Currency": "RUB",
        "AccountId": "4",
        "TestMode": "1",
    }

    with patch(
        "app.services.cloudpayments_webhook."
        "payment_service.mark_succeeded"
    ) as mark_succeeded:
        with pytest.raises(
            HTTPException
        ) as exc_info:
            service.handle_pay(
                database=database,
                payload=payload,
            )

    assert exc_info.value.status_code == 409
    assert (
        exc_info.value.detail
        == "Payment amount mismatch"
    )
    mark_succeeded.assert_not_called()


def test_currency_mismatch_is_rejected() -> None:
    service = CloudPaymentsWebhookService()

    payment = make_payment()
    subscription = make_subscription()
    database = make_database(
        payment,
        subscription,
    )

    payload = {
        "InvoiceId": "100",
        "TransactionId": "cp-test-100",
        "Amount": "199.00",
        "Currency": "USD",
        "AccountId": "4",
        "TestMode": "1",
    }

    with patch(
        "app.services.cloudpayments_webhook."
        "payment_service.mark_succeeded"
    ) as mark_succeeded:
        with pytest.raises(
            HTTPException
        ) as exc_info:
            service.handle_pay(
                database=database,
                payload=payload,
            )

    assert exc_info.value.status_code == 409
    assert (
        exc_info.value.detail
        == "Payment currency mismatch"
    )
    mark_succeeded.assert_not_called()


def test_account_mismatch_is_rejected() -> None:
    service = CloudPaymentsWebhookService()

    payment = make_payment()
    subscription = make_subscription()
    database = make_database(
        payment,
        subscription,
    )

    payload = {
        "InvoiceId": "100",
        "TransactionId": "cp-test-100",
        "Amount": "199.00",
        "Currency": "RUB",
        "AccountId": "999",
        "TestMode": "1",
    }

    with patch(
        "app.services.cloudpayments_webhook."
        "payment_service.mark_succeeded"
    ) as mark_succeeded:
        with pytest.raises(
            HTTPException
        ) as exc_info:
            service.handle_pay(
                database=database,
                payload=payload,
            )

    assert exc_info.value.status_code == 409
    assert (
        exc_info.value.detail
        == "Payment account mismatch"
    )
    mark_succeeded.assert_not_called()


def test_missing_account_id_is_rejected() -> None:
    service = CloudPaymentsWebhookService()

    payment = make_payment()
    subscription = make_subscription()
    database = make_database(
        payment,
        subscription,
    )

    payload = {
        "InvoiceId": "100",
        "TransactionId": "cp-test-100",
        "Amount": "199.00",
        "Currency": "RUB",
    }

    with patch(
        "app.services.cloudpayments_webhook."
        "payment_service.mark_succeeded"
    ) as mark_succeeded:
        with pytest.raises(
            HTTPException
        ) as exc_info:
            service.handle_pay(
                database=database,
                payload=payload,
            )

    assert exc_info.value.status_code == 400
    assert (
        exc_info.value.detail
        == "AccountId is required"
    )
    mark_succeeded.assert_not_called()


def test_valid_payment_calls_mark_succeeded() -> None:
    service = CloudPaymentsWebhookService()

    payment = make_payment()
    subscription = make_subscription()
    database = make_database(
        payment,
        subscription,
    )

    payload = {
        "InvoiceId": "100",
        "TransactionId": "cp-test-100",
        "Amount": "199.00",
        "Currency": "RUB",
        "AccountId": "4",
        "TestMode": "1",
    }

    expected_result = object()

    with patch(
        "app.services.cloudpayments_webhook."
        "payment_service.mark_succeeded",
        return_value=expected_result,
    ) as mark_succeeded:
        result = service.handle_pay(
            database=database,
            payload=payload,
        )

    assert result is expected_result

    mark_succeeded.assert_called_once_with(
        database=database,
        payment_id=100,
        provider_payment_id="cp-test-100",
    )


def test_succeeded_payment_with_other_transaction_is_rejected() -> None:
    service = CloudPaymentsWebhookService()

    payment = make_payment(
        status="succeeded",
        provider_payment_id="cp-original",
    )

    subscription = make_subscription()

    database = make_database(
        payment,
        subscription,
    )

    payload = {
        "InvoiceId": "100",
        "TransactionId": "cp-other",
        "Amount": "199.00",
        "Currency": "RUB",
        "AccountId": "4",
        "TestMode": "1",
    }

    with patch(
        "app.services.cloudpayments_webhook."
        "payment_service.mark_succeeded"
    ) as mark_succeeded:
        with pytest.raises(
            HTTPException
        ) as exc_info:
            service.handle_pay(
                database=database,
                payload=payload,
            )

    assert exc_info.value.status_code == 409
    assert (
        exc_info.value.detail
        == "Payment transaction mismatch"
    )
    mark_succeeded.assert_not_called()


def test_missing_test_mode_is_rejected() -> None:
    service = CloudPaymentsWebhookService()

    payload = {
        "InvoiceId": "100",
        "TransactionId": "cp-test-100",
        "Amount": "199.00",
        "Currency": "RUB",
        "AccountId": "4",
    }

    database = MagicMock()

    with patch(
        "app.services.cloudpayments_webhook."
        "payment_service.mark_succeeded"
    ) as mark_succeeded:
        with pytest.raises(
            HTTPException
        ) as exc_info:
            service.handle_pay(
                database=database,
                payload=payload,
            )

    assert exc_info.value.status_code == 400
    assert (
        exc_info.value.detail
        == "TestMode is required"
    )
    mark_succeeded.assert_not_called()


def test_invalid_test_mode_is_rejected() -> None:
    service = CloudPaymentsWebhookService()

    payload = {
        "InvoiceId": "100",
        "TransactionId": "cp-test-100",
        "Amount": "199.00",
        "Currency": "RUB",
        "AccountId": "4",
        "TestMode": "unexpected",
    }

    database = MagicMock()

    with patch(
        "app.services.cloudpayments_webhook."
        "payment_service.mark_succeeded"
    ) as mark_succeeded:
        with pytest.raises(
            HTTPException
        ) as exc_info:
            service.handle_pay(
                database=database,
                payload=payload,
            )

    assert exc_info.value.status_code == 400
    assert (
        exc_info.value.detail
        == "Invalid TestMode"
    )
    mark_succeeded.assert_not_called()


def test_test_webhook_is_rejected_in_live_mode() -> None:
    service = CloudPaymentsWebhookService()

    payload = {
        "InvoiceId": "100",
        "TransactionId": "cp-test-100",
        "Amount": "199.00",
        "Currency": "RUB",
        "AccountId": "4",
        "TestMode": "1",
    }

    database = MagicMock()

    with (
        patch(
            "app.services.cloudpayments_webhook."
            "settings.payment_mode",
            "live",
        ),
        patch(
            "app.services.cloudpayments_webhook."
            "payment_service.mark_succeeded"
        ) as mark_succeeded,
    ):
        with pytest.raises(
            HTTPException
        ) as exc_info:
            service.handle_pay(
                database=database,
                payload=payload,
            )

    assert exc_info.value.status_code == 409
    assert (
        exc_info.value.detail
        == "Payment mode mismatch"
    )
    mark_succeeded.assert_not_called()