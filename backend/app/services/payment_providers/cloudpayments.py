import base64
import json
from decimal import Decimal
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from fastapi import HTTPException, status

from app.core.config import settings
from app.services.payment_providers.base import (
    PaymentProvider,
    ProviderPaymentResult,
)


class CloudPaymentsProvider(PaymentProvider):

    API_URL = "https://api.cloudpayments.ru/orders/create"

    def _get_credentials(self) -> tuple[str, str]:
        public_id = settings.cloudpayments_public_id
        api_secret = settings.cloudpayments_api_secret

        if not public_id or not api_secret:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="CloudPayments is not configured",
            )

        return public_id, api_secret

    def create_payment(
        self,
        *,
        amount: Decimal,
        currency: str,
        description: str,
        idempotency_key: str,
        metadata: dict[str, str],
    ) -> ProviderPaymentResult:
        public_id, api_secret = self._get_credentials()

        payment_id = metadata.get("payment_id")
        user_id = metadata.get("user_id")

        if not payment_id or not user_id:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="CloudPayments payment metadata is incomplete",
            )

        payload = {
            "Amount": float(amount),
            "Currency": currency,
            "Description": description,
            "InvoiceId": payment_id,
            "AccountId": user_id,
            "RequireConfirmation": False,
            "SendEmail": False,
            "CultureName": "ru-RU",
        }

        if settings.payment_success_url:
            payload["SuccessRedirectUrl"] = (
                settings.payment_success_url
            )

        if settings.payment_fail_url:
            payload["FailRedirectUrl"] = (
                settings.payment_fail_url
            )

        body = json.dumps(
            payload,
            ensure_ascii=False,
        ).encode("utf-8")

        credentials = (
            f"{public_id}:{api_secret}"
        ).encode("utf-8")

        basic_auth = base64.b64encode(
            credentials
        ).decode("ascii")

        request = Request(
            self.API_URL,
            data=body,
            method="POST",
            headers={
                "Authorization": f"Basic {basic_auth}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "X-Request-ID": idempotency_key,
            },
        )

        try:
            with urlopen(
                request,
                timeout=15,
            ) as response:
                raw_response = response.read()

        except HTTPError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="CloudPayments rejected payment creation",
            ) from exc

        except URLError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="CloudPayments unavailable",
            ) from exc

        try:
            response_data = json.loads(
                raw_response.decode("utf-8")
            )
        except (
            UnicodeDecodeError,
            json.JSONDecodeError,
        ) as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Invalid CloudPayments response",
            ) from exc

        if response_data.get("Success") is not True:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="CloudPayments payment creation failed",
            )

        model = response_data.get("Model")

        if not isinstance(model, dict):
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Invalid CloudPayments payment response",
            )

        provider_payment_id = model.get("Id")
        confirmation_url = model.get("Url")

        if not provider_payment_id or not confirmation_url:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="CloudPayments did not return payment URL",
            )

        return ProviderPaymentResult(
            provider_payment_id=str(
                provider_payment_id
            ),
            confirmation_url=str(
                confirmation_url
            ),
        )

    def cancel_payment(
        self,
        *,
        provider_payment_id: str,
    ) -> None:
        public_id, api_secret = self._get_credentials()

        payload = {
            "Id": provider_payment_id,
        }

        body = json.dumps(
            payload,
            ensure_ascii=False,
        ).encode("utf-8")

        credentials = (
            f"{public_id}:{api_secret}"
        ).encode("utf-8")

        basic_auth = base64.b64encode(
            credentials
        ).decode("ascii")

        request = Request(
            "https://api.cloudpayments.ru/orders/cancel",
            data=body,
            method="POST",
            headers={
                "Authorization": f"Basic {basic_auth}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )

        try:
            with urlopen(
                request,
                timeout=15,
            ) as response:
                raw_response = response.read()

        except HTTPError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="CloudPayments rejected payment cancellation",
            ) from exc

        except URLError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="CloudPayments unavailable",
            ) from exc

        try:
            response_data = json.loads(
                raw_response.decode("utf-8")
            )
        except (
            UnicodeDecodeError,
            json.JSONDecodeError,
        ) as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Invalid CloudPayments response",
            ) from exc

        if response_data.get("Success") is not True:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="CloudPayments payment cancellation failed",
            )
