from datetime import datetime

from pydantic import BaseModel, Field


class SubscriptionTokenCreate(BaseModel):
    telegram_id: int


class SubscriptionTokenRead(BaseModel):
    access_key: str
    subscription_url: str
    connect_url: str
    created_at: datetime
    rotated_at: datetime | None
    mobile_access_key: str | None = None
    mobile_subscription_url: str | None = None
    mobile_connect_url: str | None = None
    basic_device_connect_urls: dict[str, str] = Field(default_factory=dict)
    mobile_device_connect_urls: dict[str, str] = Field(default_factory=dict)
