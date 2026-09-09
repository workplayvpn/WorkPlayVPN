from datetime import datetime

from pydantic import BaseModel


class MiniAppUserRead(BaseModel):
    telegram_id: int
    first_name: str
    username: str | None


class MiniAppSubscriptionRead(BaseModel):
    status: str
    plan_code: str
    plan_name: str
    starts_at: datetime | None
    expires_at: datetime | None


class MiniAppDeviceSummaryRead(BaseModel):
    active_count: int
    total_limit: int


class MiniAppMeRead(BaseModel):
    user: MiniAppUserRead
    subscription: MiniAppSubscriptionRead | None
    devices: MiniAppDeviceSummaryRead
    trial_available: bool
