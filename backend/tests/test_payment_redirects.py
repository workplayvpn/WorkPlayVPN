from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.dependencies import get_db
from app.main import app
from app.models.payment import Payment
from app.core.config import settings
from app.services.payment_redirect_service import (
    payment_redirect_service,
)


ROBOKASSA_URL = (
    "https://auth.robokassa.ru/Merchant/Index.aspx"
    "?MerchantLogin=workplayvpn"
    "&OutSum=199.00"
    "&InvId=123"
    "&SignatureValue=secret-signature&Receipt=encoded-receipt"
)


@pytest.fixture(autouse=True)
def checkout_environment(monkeypatch):
    monkeypatch.setattr(settings, "payment_mode", "live")
    monkeypatch.setattr(settings, "robokassa_is_test", False)
    monkeypatch.setattr(settings, "robokassa_merchant_login", "workplayvpn")


def build_payment(
    *,
    status: str = "pending",
    expires_at: datetime | None = None,
    confirmation_url: str = ROBOKASSA_URL,
) -> Payment:
    now = datetime.now(UTC)

    return Payment(
        id=123,
        user_id=456,
        subscription_id=789,
        provider="robokassa",
        purpose="subscription",
        provider_payment_id="robokassa:123",
        idempotency_key="payment-redirect-test",
        status=status,
        amount=Decimal("199.00"),
        currency="RUB",
        confirmation_url=confirmation_url,
        created_at=now,
        updated_at=now,
        expires_at=expires_at or (
            now + timedelta(minutes=30)
        ),
    )


def test_builds_short_public_confirmation_url() -> None:
    payment = build_payment()

    result = (
        payment_redirect_service
        .build_public_confirmation_url(payment)
    )

    assert result is not None
    assert result.startswith(
        "https://connect.workplayvpn.ru/pay/123."
    )
    assert "auth.robokassa.ru" not in result
    assert "SignatureValue" not in result


def test_valid_token_resolves_robokassa_url() -> None:
    payment = build_payment()
    database = Mock(spec=Session)
    database.get.return_value = payment

    token = payment_redirect_service.build_token(
        payment.id
    )

    result = (
        payment_redirect_service
        .resolve_confirmation_url(
            database=database,
            raw_token=token,
        )
    )

    assert result == ROBOKASSA_URL
    database.get.assert_called_once_with(
        Payment,
        payment.id,
    )


def test_tampered_token_is_rejected() -> None:
    database = Mock(spec=Session)

    with pytest.raises(HTTPException) as exc_info:
        (
            payment_redirect_service
            .resolve_confirmation_url(
                database=database,
                raw_token="123.invalid-signature",
            )
        )

    assert exc_info.value.status_code == 404
    database.get.assert_not_called()


def test_completed_payment_link_is_rejected() -> None:
    payment = build_payment(status="succeeded")
    database = Mock(spec=Session)
    database.get.return_value = payment

    token = payment_redirect_service.build_token(
        payment.id
    )

    with pytest.raises(HTTPException) as exc_info:
        (
            payment_redirect_service
            .resolve_confirmation_url(
                database=database,
                raw_token=token,
            )
        )

    assert exc_info.value.status_code == 410


def test_expired_payment_link_is_rejected() -> None:
    payment = build_payment(
        expires_at=(
            datetime.now(UTC)
            - timedelta(minutes=1)
        ),
    )
    database = Mock(spec=Session)
    database.get.return_value = payment

    token = payment_redirect_service.build_token(
        payment.id
    )

    with pytest.raises(HTTPException) as exc_info:
        (
            payment_redirect_service
            .resolve_confirmation_url(
                database=database,
                raw_token=token,
            )
        )

    assert exc_info.value.status_code == 410


def test_external_redirect_is_rejected() -> None:
    payment = build_payment(
        confirmation_url=(
            "https://example.com/fake-payment"
        ),
    )
    database = Mock(spec=Session)
    database.get.return_value = payment

    token = payment_redirect_service.build_token(
        payment.id
    )

    with pytest.raises(HTTPException) as exc_info:
        (
            payment_redirect_service
            .resolve_confirmation_url(
                database=database,
                raw_token=token,
            )
        )

    assert exc_info.value.status_code == 503


def test_public_endpoint_redirects_without_cache() -> None:
    payment = build_payment()
    database = Mock(spec=Session)
    database.get.return_value = payment

    def override_get_db():
        yield database

    app.dependency_overrides[get_db] = override_get_db

    try:
        client = TestClient(app)
        token = payment_redirect_service.build_token(
            payment.id
        )

        response = client.get(
            f"/pay/{token}",
            follow_redirects=False,
        )
    finally:
        app.dependency_overrides.pop(
            get_db,
            None,
        )

    assert response.status_code == 302
    assert response.headers["location"] == ROBOKASSA_URL
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert response.headers["x-robots-tag"] == (
        "noindex, nofollow, noarchive"
    )

def test_test_invoice_is_not_available_in_live_mode():
    payment = build_payment(confirmation_url=ROBOKASSA_URL + "&IsTest=1")
    database = Mock(spec=Session)
    database.get.return_value = payment
    with pytest.raises(HTTPException) as error:
        payment_redirect_service.resolve_confirmation_url(
            database=database, raw_token=payment_redirect_service.build_token(payment.id)
        )
    assert error.value.status_code == 410
