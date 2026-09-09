from datetime import datetime
from decimal import Decimal

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


class MiniAppPlanRead(BaseModel):
    code: str
    name: str
    duration_days: int
    price_amount: Decimal
    currency: str
    device_limit: int


class MiniAppLocationRead(BaseModel):
    code: str
    name: str


class MiniAppCatalogRead(BaseModel):
    plans: list[MiniAppPlanRead]
    locations: list[MiniAppLocationRead]
