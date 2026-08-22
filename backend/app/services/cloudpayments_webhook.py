import base64
import hashlib
import hmac
from decimal import Decimal, InvalidOperation
from urllib.parse import unquote_plus

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.payment import Payment
from app.models.subscription import Subscription
from app.services.payment_service import payment_service


class CloudPaymentsWebhookService:

    def _get_api_secret(self) -> str:
        api_secret = settings.cloudpayments_api_secret

        if not api_secret:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="CloudPayments is not configured",
            )

        return api_secret

    def _calculate_hmac(
        self,
        message: bytes,
    ) -> str:
        api_secret = self._get_api_secret()

        digest = hmac.new(
            api_secret.encode("utf-8"),
            message,
            hashlib.sha256,
        ).digest()

        return base64.b64encode(
            digest
        ).decode("ascii")

    def verify_signature(
        self,
        *,
        raw_body: bytes,
        x_content_hmac: str | None,
        content_hmac: str | None,
    ) -> None:
        if not x_content_hmac and not content_hmac:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="CloudPayments signature missing",
            )

        signatures_match = False

        # Content-HMAC:
        # подпись URL-encoded тела POST-запроса.
        if content_hmac:
            expected_content_hmac = self._calculate_hmac(
                raw_body
            )

            if hmac.compare_digest(
                expected_content_hmac,
                content_hmac,
            ):
                signatures_match = True

        # X-Content-HMAC:
        # подпись URL-decoded представления параметров.
        if x_content_hmac:
            try:
                decoded_body = unquote_plus(
                    raw_body.decode("utf-8")
                ).encode("utf-8")
            except UnicodeDecodeError as exc:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid webhook encoding",
                ) from exc

            expected_x_content_hmac = self._calculate_hmac(
                decoded_body
            )

            if hmac.compare_digest(
                expected_x_content_hmac,
                x_content_hmac,
            ):
                signatures_match = True

        if not signatures_match:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid CloudPayments signature",
            )

    def parse_payload(
        self,
        raw_body: bytes,
    ) -> dict[str, str]:
        from urllib.parse import parse_qs

        try:
            decoded_body = raw_body.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid webhook encoding",
            ) from exc

        parsed = parse_qs(
            decoded_body,
            keep_blank_values=True,
        )

        return {
            key: values[-1]
            for key, values in parsed.items()
            if values
        }

    def handle_pay(
        self,
        *,
        database: Session,
        payload: dict[str, str],
    ) -> Payment:
        invoice_id = payload.get("InvoiceId")
        transaction_id = payload.get("TransactionId")
        amount_raw = payload.get("Amount")
        currency = payload.get("Currency")
        account_id = payload.get("AccountId")

        if not invoice_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="InvoiceId is required",
            )

        if not transaction_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="TransactionId is required",
            )

        if amount_raw is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Amount is required",
            )

        if not currency:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Currency is required",
            )

        if not account_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="AccountId is required",
            )

        try:
            payment_id = int(invoice_id)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid InvoiceId",
            ) from exc

        try:
            webhook_amount = Decimal(amount_raw)
        except InvalidOperation as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid Amount",
            ) from exc

        payment = database.get(
            Payment,
            payment_id,
        )

        if payment is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Payment not found",
            )

        if payment.provider != "cloudpayments":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Payment provider mismatch",
            )

        subscription = database.get(
            Subscription,
            payment.subscription_id,
        )

        if subscription is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Payment subscription not found",
            )

        if webhook_amount != payment.amount:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Payment amount mismatch",
            )

        if currency != payment.currency:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Payment currency mismatch",
            )

        if account_id != str(payment.user_id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Payment account mismatch",
            )

        if (
            payment.status == "succeeded"
            and payment.provider_payment_id
            and payment.provider_payment_id
            != str(transaction_id)
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Payment transaction mismatch",
            )

        return payment_service.mark_succeeded(
            database=database,
            payment_id=payment.id,
            provider_payment_id=str(transaction_id),
        )


cloudpayments_webhook_service = (
    CloudPaymentsWebhookService()
)