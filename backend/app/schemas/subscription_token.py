from datetime import datetime

from pydantic import BaseModel


class SubscriptionTokenCreate(BaseModel):
    telegram_id: int


class SubscriptionTokenRead(BaseModel):
    subscription_url: str
    created_at: datetime
    rotated_at: datetime | None = None