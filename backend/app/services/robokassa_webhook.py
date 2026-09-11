import hmac
from decimal import Decimal, InvalidOperation
from urllib.parse import parse_qs

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.payment import Payment
from app.services.payment_providers.robokassa import (
    calculate_robokassa_signature,
)
from app.services.payment_service import payment_service


class RobokassaWebhookService:

    def _get_password_2(self) -> str:
        password_2 = settings.robokassa_password_2

        if not password_2:
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

        return password_2

    def parse_payload(
        self,
        raw_body: bytes,
    ) -> dict[str, str]:
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

    def verify_signature(
        self,
        payload: dict[str, str],
    ) -> None:
        out_sum = payload.get("OutSum")
        invoice_id = payload.get("InvId")
        signature = payload.get("SignatureValue")

        if out_sum is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="OutSum is required",
            )

        if not invoice_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="InvId is required",
            )

        if not signature:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Robokassa signature missing",
            )

        password_2 = self._get_password_2()
        signature_parts = [
            out_sum,
            invoice_id,
            password_2,
        ]

        signature_parts.extend(
            f"{key}={payload[key]}"
            for key in sorted(payload)
            if key.startswith("Shp_")
        )

        expected_signature = (
            calculate_robokassa_signature(
                parts=signature_parts,
                algorithm=(
                    settings.robokassa_hash_algorithm
                ),
            )
        )

        if not hmac.compare_digest(
            expected_signature.lower(),
            signature.lower(),
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Robokassa signature",
            )

    def handle_result(
        self,
        *,
        database: Session,
        payload: dict[str, str],
    ) -> Payment:
        invoice_id = payload.get("InvId")
        amount_raw = payload.get("OutSum")

        if not invoice_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="InvId is required",
            )

        if amount_raw is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="OutSum is required",
            )

        try:
            payment_id = int(invoice_id)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid InvId",
            ) from exc

        if payment_id <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid InvId",
            )

        try:
            webhook_amount = Decimal(amount_raw)
        except InvalidOperation as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid OutSum",
            ) from exc

        if not webhook_amount.is_finite():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid OutSum",
            )

        payment = database.get(Payment, payment_id)

        if payment is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Payment not found",
            )

        if payment.provider != "robokassa":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Payment provider mismatch",
            )

        if payment.currency != "RUB":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Payment currency mismatch",
            )

        if webhook_amount != payment.amount:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Payment amount mismatch",
            )

        provider_payment_id = f"robokassa:{invoice_id}"

        if (
            payment.provider_payment_id is not None
            and payment.provider_payment_id
            != provider_payment_id
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Payment transaction mismatch",
            )

        return payment_service.mark_succeeded(
            database=database,
            payment_id=payment.id,
            provider_payment_id=provider_payment_id,
        )


robokassa_webhook_service = RobokassaWebhookService()
