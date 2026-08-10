from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SubscriptionCreate(BaseModel):
    telegram_id: int
    plan_code: str


class SubscriptionRead(BaseModel):
    id: int
    user_id: int
    plan_id: int
    status: str
    starts_at: datetime | None
    expires_at: datetime | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class SubscriptionStatusRead(BaseModel):
    status: str
    plan_code: str
    plan_name: str
    starts_at: datetime | None
    expires_at: datetime | None
    included_devices: int
    extra_device_slots: int
    total_device_limit: int