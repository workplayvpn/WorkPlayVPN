import hashlib
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from urllib.parse import urlencode

from fastapi import HTTPException, status

from app.core.config import settings
from app.services.payment_providers.base import (
    PaymentProvider,
    ProviderPaymentResult,
)


SUPPORTED_HASH_ALGORITHMS = {
    "md5",
    "sha1",
    "sha256",
    "sha384",
    "sha512",
}


def calculate_robokassa_signature(
    *,
    parts: list[str],
    algorithm: str,
) -> str:
    normalized_algorithm = algorithm.strip().lower()

    if normalized_algorithm not in SUPPORTED_HASH_ALGORITHMS:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unsupported Robokassa hash algorithm",
        )

    message = ":".join(parts).encode("utf-8")

    return hashlib.new(
        normalized_algorithm,
        message,
    ).hexdigest()


class RobokassaProvider(PaymentProvider):

    PAYMENT_URL = (
        "https://auth.robokassa.ru/Merchant/Index.aspx"
    )
    MOSCOW_TIMEZONE = timezone(timedelta(hours=3))

    def _get_credentials(self) -> tuple[str, str]:
        merchant_login = settings.robokassa_merchant_login
        password_1 = settings.robokassa_password_1

        if not merchant_login or not password_1:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Robokassa is not configured",
            )

        expected_test_mode = settings.payment_mode == "test"

        if settings.robokassa_is_test != expected_test_mode:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Robokassa payment mode is inconsistent",
            )

        return merchant_login, password_1

    def _format_expiration(
        self,
        raw_expiration: str | None,
    ) -> str | None:
        if not raw_expiration:
            return None

        try:
            expiration = datetime.fromisoformat(
                raw_expiration
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Invalid payment expiration",
            ) from exc

        if expiration.tzinfo is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Payment expiration timezone is missing",
            )

        return expiration.astimezone(
            self.MOSCOW_TIMEZONE
        ).strftime("%Y-%m-%dT%H:%M")

    def create_payment(
        self,
        *,
        amount: Decimal,
        currency: str,
        description: str,
        idempotency_key: str,
        metadata: dict[str, str],
    ) -> ProviderPaymentResult:
        del idempotency_key

        merchant_login, password_1 = (
            self._get_credentials()
        )

        if currency != "RUB":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Robokassa supports RUB payments only",
            )

        payment_id = metadata.get("payment_id")

        if not payment_id or not payment_id.isdecimal():
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Robokassa payment metadata is incomplete",
            )

        amount_value = format(
            amount.quantize(Decimal("0.01")),
            "f",
        )

        signature = calculate_robokassa_signature(
            parts=[
                merchant_login,
                amount_value,
                payment_id,
                password_1,
            ],
            algorithm=settings.robokassa_hash_algorithm,
        )

        parameters = {
            "MerchantLogin": merchant_login,
            "OutSum": amount_value,
            "InvId": payment_id,
            "Description": description[:100],
            "SignatureValue": signature,
            "Culture": "ru",
            "Encoding": "utf-8",
        }

        expiration = self._format_expiration(
            metadata.get("expires_at")
        )

        if expiration:
            parameters["ExpirationDate"] = expiration

        if settings.robokassa_is_test:
            parameters["IsTest"] = "1"

        confirmation_url = (
            f"{self.PAYMENT_URL}?{urlencode(parameters)}"
        )

        return ProviderPaymentResult(
            provider_payment_id=f"robokassa:{payment_id}",
            confirmation_url=confirmation_url,
        )

    def cancel_payment(
        self,
        *,
        provider_payment_id: str,
    ) -> None:
        del provider_payment_id
