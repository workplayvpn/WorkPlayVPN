from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class PaymentCreate(BaseModel):
    telegram_id: int
    plan_code: str
    provider: str | None = None
    idempotency_key: str | None = None


class PaymentRead(BaseModel):
    id: int
    subscription_id: int
    provider: str
    provider_payment_id: str | None
    status: str
    amount: Decimal
    currency: str
    confirmation_url: str | None
    created_at: datetime
    expires_at: datetime | None
    paid_at: datetime | None


class PaymentComplete(BaseModel):
    provider_payment_id: str | None = None

class PaymentCancel(BaseModel):
    telegram_id: int