from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class PlanRead(BaseModel):
    id: int
    code: str
    name: str
    duration_days: int
    price_amount: Decimal
    currency: str
    device_limit: int

    model_config = ConfigDict(from_attributes=True)


class LocationRead(BaseModel):
    id: int
    code: str
    name: str
    is_active: bool

    model_config = ConfigDict(from_attributes=True)