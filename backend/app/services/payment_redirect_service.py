import base64
import hashlib
import hmac
from datetime import UTC, datetime
from urllib.parse import urlsplit

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.payment import Payment
from app.services.payment_checkout import effective_payment_expiry, payment_matches_environment


class PaymentRedirectService:

    SIGNATURE_BYTES = 16
    ROBOKASSA_HOST = "auth.robokassa.ru"

    def _not_found(self) -> HTTPException:
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment link not found",
        )

    def _sign(
        self,
        payment_id: int,
    ) -> str:
        message = (
            f"payment-redirect:v1:{payment_id}"
        ).encode("utf-8")

        digest = hmac.new(
            settings.internal_api_secret.encode("utf-8"),
            message,
            hashlib.sha256,
        ).digest()[:self.SIGNATURE_BYTES]

        return (
            base64.urlsafe_b64encode(digest)
            .decode("ascii")
            .rstrip("=")
        )

    def build_token(
        self,
        payment_id: int,
    ) -> str:
        signature = self._sign(payment_id)

        return f"{payment_id}.{signature}"

    def build_public_confirmation_url(
        self,
        payment: Payment,
    ) -> str | None:
        confirmation_url = payment.confirmation_url

        if (
            payment.provider != "robokassa"
            or not confirmation_url
        ):
            return confirmation_url

        token = self.build_token(payment.id)
        base_url = (
            settings.payment_redirect_base_url.rstrip("/")
        )

        return f"{base_url}/{token}"

    def resolve_confirmation_url(
        self,
        *,
        database: Session,
        raw_token: str,
    ) -> str:
        parts = raw_token.split(".", maxsplit=1)

        if len(parts) != 2:
            raise self._not_found()

        payment_id_raw, provided_signature = parts

        if not payment_id_raw.isdecimal():
            raise self._not_found()

        payment_id = int(payment_id_raw)

        if payment_id <= 0:
            raise self._not_found()

        expected_signature = self._sign(payment_id)

        if not hmac.compare_digest(
            expected_signature,
            provided_signature,
        ):
            raise self._not_found()

        payment = database.get(Payment, payment_id)

        if (
            payment is None
            or payment.provider != "robokassa"
            or not payment.confirmation_url
        ):
            raise self._not_found()

        if payment.status != "pending":
            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail="Payment link is no longer available",
            )

        expires_at = effective_payment_expiry(payment)

        if expires_at is not None:
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=UTC)

            if expires_at <= datetime.now(UTC):
                raise HTTPException(
                    status_code=status.HTTP_410_GONE,
                    detail="Payment link has expired",
                )

        parsed_url = urlsplit(
            payment.confirmation_url
        )

        if (
            parsed_url.scheme != "https"
            or parsed_url.hostname
            != self.ROBOKASSA_HOST
            or parsed_url.username is not None
            or parsed_url.password is not None
            or parsed_url.port not in (None, 443)
        ):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Payment confirmation URL is invalid",
            )

        if not payment_matches_environment(payment):
            raise HTTPException(status_code=410, detail="Payment belongs to another payment environment")

        return payment.confirmation_url


payment_redirect_service = PaymentRedirectService()