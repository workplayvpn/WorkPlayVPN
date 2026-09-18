from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


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
    available: bool


class MiniAppCatalogRead(BaseModel):
    plans: list[MiniAppPlanRead]
    locations: list[MiniAppLocationRead]


class MiniAppActivationCreate(BaseModel):
    location_code: str = Field(min_length=1, max_length=50)


class MiniAppActivationRead(BaseModel):
    activation_id: int
    expires_at: datetime
    activation_url: str


class MiniAppDeviceCreate(BaseModel):
    location_code: str = Field(min_length=1, max_length=50)
    device_name: str = Field(min_length=1, max_length=100)
    platform: str | None = Field(default=None, max_length=50)


class MiniAppDeviceRead(BaseModel):
    id: int
    device_name: str = Field(min_length=1, max_length=100)
    node_code: str = Field(min_length=1, max_length=50)
    node_name: str
    is_active: bool
    created_at: datetime


class MiniAppPaymentCreate(BaseModel):
    plan_code: str = Field(min_length=1, max_length=50)
    idempotency_key: str = Field(min_length=16, max_length=255)


class MiniAppPaymentRead(BaseModel):
    id: int
    status: str
    amount: Decimal
    currency: str
    confirmation_url: str | None
    created_at: datetime
    expires_at: datetime | None
    paid_at: datetime | None
