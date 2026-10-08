import hashlib
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.models.payment import Payment
from app.services.robokassa_webhook import (
    RobokassaWebhookService,
)


TEST_PASSWORD_2 = "test-password-2"


def make_payment(
    *,
    payment_id: int = 100,
    provider: str = "robokassa",
    amount: Decimal = Decimal("199.00"),
    currency: str = "RUB",
    provider_payment_id: str | None = "robokassa:100",
):
    return SimpleNamespace(
        id=payment_id,
        provider=provider,
        amount=amount,
        currency=currency,
        provider_payment_id=provider_payment_id,
    )


def make_database(payment):
    database = MagicMock()
    database.scalar.return_value = None

    def get_side_effect(model, object_id):
        if model is Payment and object_id == payment.id:
            return payment
        return None

    database.get.side_effect = get_side_effect
    return database


def make_signature(
    *,
    out_sum: str = "199.00",
    invoice_id: str = "100",
) -> str:
    message = (
        f"{out_sum}:{invoice_id}:{TEST_PASSWORD_2}"
    ).encode("utf-8")
    return hashlib.sha256(message).hexdigest()


def settings_patches():
    return (
        patch(
            "app.services.robokassa_webhook."
            "settings.robokassa_password_2",
            TEST_PASSWORD_2,
        ),
        patch(
            "app.services.robokassa_webhook."
            "settings.robokassa_hash_algorithm",
            "sha256",
        ),
        patch(
            "app.services.robokassa_webhook."
            "settings.robokassa_is_test",
            True,
        ),
        patch(
            "app.services.robokassa_webhook."
            "settings.payment_mode",
            "test",
        ),
    )


def test_parse_payload() -> None:
    service = RobokassaWebhookService()

    payload = service.parse_payload(
        b"OutSum=199.00&InvId=100&SignatureValue=ABC"
    )

    assert payload == {
        "OutSum": "199.00",
        "InvId": "100",
        "SignatureValue": "ABC",
    }


def test_valid_signature() -> None:
    service = RobokassaWebhookService()
    payload = {
        "OutSum": "199.00",
        "InvId": "100",
        "SignatureValue": make_signature(),
    }

    patches = settings_patches()
    with patches[0], patches[1], patches[2], patches[3]:
        service.verify_signature(payload)


def test_invalid_signature_is_rejected() -> None:
    service = RobokassaWebhookService()
    payload = {
        "OutSum": "199.00",
        "InvId": "100",
        "SignatureValue": "invalid",
    }

    patches = settings_patches()
    with patches[0], patches[1], patches[2], patches[3]:
        with pytest.raises(HTTPException) as exc_info:
            service.verify_signature(payload)

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == (
        "Invalid Robokassa signature"
    )


def test_valid_payment_calls_mark_succeeded() -> None:
    service = RobokassaWebhookService()
    payment = make_payment()
    database = make_database(payment)
    payload = {
        "OutSum": "199.00",
        "InvId": "100",
    }
    expected_result = object()

    with patch(
        "app.services.robokassa_webhook."
        "payment_service.mark_succeeded",
        return_value=expected_result,
    ) as mark_succeeded:
        result = service.handle_result(
            database=database,
            payload=payload,
        )

    assert result is expected_result
    mark_succeeded.assert_called_once_with(
        database=database,
        payment_id=100,
        provider_payment_id="robokassa:100",
    )


def test_amount_mismatch_is_rejected() -> None:
    service = RobokassaWebhookService()
    payment = make_payment()
    database = make_database(payment)
    payload = {
        "OutSum": "198.00",
        "InvId": "100",
    }

    with patch(
        "app.services.robokassa_webhook."
        "payment_service.mark_succeeded"
    ) as mark_succeeded:
        with pytest.raises(HTTPException) as exc_info:
            service.handle_result(
                database=database,
                payload=payload,
            )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == (
        "Payment amount mismatch"
    )
    mark_succeeded.assert_not_called()


def test_provider_mismatch_is_rejected() -> None:
    service = RobokassaWebhookService()
    payment = make_payment(provider="cloudpayments")
    database = make_database(payment)
    payload = {
        "OutSum": "199.00",
        "InvId": "100",
    }

    with patch(
        "app.services.robokassa_webhook."
        "payment_service.mark_succeeded"
    ) as mark_succeeded:
        with pytest.raises(HTTPException) as exc_info:
            service.handle_result(
                database=database,
                payload=payload,
            )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == (
        "Payment provider mismatch"
    )
    mark_succeeded.assert_not_called()


def test_transaction_mismatch_is_rejected() -> None:
    service = RobokassaWebhookService()
    payment = make_payment(
        provider_payment_id="different",
    )
    database = make_database(payment)
    payload = {
        "OutSum": "199.00",
        "InvId": "100",
    }

    with patch(
        "app.services.robokassa_webhook."
        "payment_service.mark_succeeded"
    ) as mark_succeeded:
        with pytest.raises(HTTPException) as exc_info:
            service.handle_result(
                database=database,
                payload=payload,
            )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == (
        "Payment transaction mismatch"
    )
    mark_succeeded.assert_not_called()


def test_signature_with_shp_parameters() -> None:
    service = RobokassaWebhookService()
    payload = {
        "OutSum": "199.00",
        "InvId": "100",
        "Shp_beta": "2",
        "Shp_alpha": "1",
    }
    message = (
        "199.00:100:test-password-2:"
        "Shp_alpha=1:Shp_beta=2"
    ).encode("utf-8")
    payload["SignatureValue"] = hashlib.sha256(
        message
    ).hexdigest()

    patches = settings_patches()
    with patches[0], patches[1], patches[2], patches[3]:
        service.verify_signature(payload)


def test_mode_mismatch_is_rejected() -> None:
    service = RobokassaWebhookService()
    payload = {
        "OutSum": "199.00",
        "InvId": "100",
        "SignatureValue": make_signature(),
    }

    with (
        patch(
            "app.services.robokassa_webhook."
            "settings.robokassa_password_2",
            TEST_PASSWORD_2,
        ),
        patch(
            "app.services.robokassa_webhook."
            "settings.robokassa_is_test",
            False,
        ),
        patch(
            "app.services.robokassa_webhook."
            "settings.payment_mode",
            "test",
        ),
    ):
        with pytest.raises(HTTPException) as exc_info:
            service.verify_signature(payload)

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == (
        "Robokassa payment mode is inconsistent"
    )


def test_public_invoice_number_is_resolved_to_internal_payment():
    payment = make_payment(payment_id=100, provider_payment_id="robokassa:422415962178")
    database = make_database(payment)
    database.scalar.return_value = payment
    service = RobokassaWebhookService()
    with patch("app.services.robokassa_webhook.payment_service.mark_succeeded", return_value=payment) as mark:
        result = service.handle_result(database=database, payload={"InvId": "422415962178", "OutSum": "199.00"})
    assert result is payment
    mark.assert_called_once_with(database=database, payment_id=100, provider_payment_id="robokassa:422415962178")
    database.get.assert_not_called()
