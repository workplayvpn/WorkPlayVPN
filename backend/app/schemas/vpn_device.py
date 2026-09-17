from datetime import datetime

from pydantic import BaseModel, Field


class VpnDeviceCreate(BaseModel):
    telegram_id: int
    node_code: str = "nl-01"
    device_name: str = Field(min_length=1, max_length=100)


class VpnDeviceLocationUpdate(BaseModel):
    telegram_id: int
    location_code: str = Field(min_length=1, max_length=50)


class VpnDeviceRead(BaseModel):
    id: int
    device_name: str
    node_code: str
    node_name: str
    is_active: bool
    created_at: datetime
    vless_url: str | None = None
