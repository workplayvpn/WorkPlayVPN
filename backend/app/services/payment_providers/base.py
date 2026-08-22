from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal


@dataclass(slots=True)
class ProviderPaymentResult:
    provider_payment_id: str
    confirmation_url: str | None


class PaymentProvider(ABC):

    @abstractmethod
    def create_payment(
        self,
        *,
        amount: Decimal,
        currency: str,
        description: str,
        idempotency_key: str,
        metadata: dict[str, str],
    ) -> ProviderPaymentResult:
        raise NotImplementedError