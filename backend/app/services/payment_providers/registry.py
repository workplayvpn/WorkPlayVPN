from fastapi import HTTPException, status

from app.services.payment_providers.base import PaymentProvider
from app.services.payment_providers.test import TestPaymentProvider


class PaymentProviderRegistry:

    def __init__(self) -> None:
        self._providers: dict[str, PaymentProvider] = {
            "test": TestPaymentProvider(),
        }

    def get(
        self,
        provider_name: str,
    ) -> PaymentProvider:
        provider = self._providers.get(
            provider_name
        )

        if provider is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unsupported payment provider",
            )

        return provider


payment_provider_registry = PaymentProviderRegistry()