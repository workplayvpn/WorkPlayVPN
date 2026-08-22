import uuid
from decimal import Decimal

from app.services.payment_providers.base import (
    PaymentProvider,
    ProviderPaymentResult,
)


class TestPaymentProvider(PaymentProvider):

    def __init__(self) -> None:
        self._failed_once_keys: set[str] = set()

    def create_payment(
        self,
        *,
        amount: Decimal,
        currency: str,
        description: str,
        idempotency_key: str,
        metadata: dict[str, str],
    ) -> ProviderPaymentResult:
        if (
            idempotency_key.startswith("fail-once-")
            and idempotency_key not in self._failed_once_keys
        ):
            self._failed_once_keys.add(
                idempotency_key
            )

            raise RuntimeError(
                "Simulated payment provider failure"
            )

        provider_payment_id = (
            f"test_{uuid.uuid4().hex}"
        )

        confirmation_url = (
            "https://example.com/"
            f"payments/{provider_payment_id}"
        )

        return ProviderPaymentResult(
            provider_payment_id=provider_payment_id,
            confirmation_url=confirmation_url,
        )