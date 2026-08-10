from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class UserCreate(BaseModel):
    telegram_id: int = Field(gt=0)
    username: str | None = Field(
        default=None,
        max_length=255,
    )
    first_name: str | None = Field(
        default=None,
        max_length=255,
    )


class UserRead(BaseModel):
    id: int
    telegram_id: int
    username: str | None
    first_name: str | None
    is_active: bool
    extra_device_slots: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)