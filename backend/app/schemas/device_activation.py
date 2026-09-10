from datetime import datetime

from pydantic import BaseModel


class DeviceActivationCreate(BaseModel):
    telegram_id: int
    location_code: str


class DeviceActivationRead(BaseModel):
    activation_id: int
    expires_at: datetime
    activation_url: str


class DeviceActivationComplete(BaseModel):
    device_name: str
    platform: str | None = None


class DeviceActivationCompleteRead(BaseModel):
    device_id: int
    device_name: str
    node_code: str
    node_name: str
    platform: str | None = None
    vless_url: str | None = None