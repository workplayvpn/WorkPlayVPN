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
    access_tier: str = "basic"


class MiniAppDeviceSummaryRead(BaseModel):
    active_count: int
    total_limit: int


class MiniAppRegionRead(BaseModel):
    code: str = Field(min_length=1, max_length=50)
    name: str


class MiniAppRegionUpdate(BaseModel):
    location_code: str = Field(min_length=1, max_length=50)


class MiniAppMeRead(BaseModel):
    user: MiniAppUserRead
    subscription: MiniAppSubscriptionRead | None
    devices: MiniAppDeviceSummaryRead
    current_region: MiniAppRegionRead | None
    trial_available: bool
    subscriptions: list[MiniAppSubscriptionRead] = Field(default_factory=list)
    connect_urls: dict[str, str] = Field(default_factory=dict)
    auto_connect_urls: dict[str, str] = Field(default_factory=dict)
    basic_device_connect_urls: dict[str, str] = Field(default_factory=dict)


class MiniAppPlanRead(BaseModel):
    code: str
    name: str
    duration_days: int
    price_amount: Decimal
    currency: str
    device_limit: int
    access_tier: str


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
    device_name: str = Field(min_length=1, max_length=100)
    platform: str | None = Field(default=None, max_length=50)
    client_instance_id: str = Field(
        min_length=16,
        max_length=64,
        pattern=r"^[A-Za-z0-9._:-]+$",
    )


class MiniAppDeviceRead(BaseModel):
    id: int
    public_id: str
    happ_device_model: str | None = None
    happ_device_os: str | None = None
    device_name: str = Field(min_length=1, max_length=100)
    node_code: str = Field(min_length=1, max_length=50)
    node_name: str
    is_active: bool
    created_at: datetime


class MiniAppDeviceCreateRead(MiniAppDeviceRead):
    connect_url: str
    mobile_connect_url: str | None = None


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
    plan_code: str | None = None
    plan_name: str | None = None
    duration_days: int | None = None
    access_tier: str | None = None
    purpose: str = "subscription"
