from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class PlateDetectionRequest(BaseModel):
    plate: str = Field(..., min_length=4, max_length=20)


class DisplayResponse(BaseModel):
    version: int
    text: str
    status: str


class BonusPressRequest(BaseModel):
    plate: str | None = None


class BonusPressResponse(BaseModel):
    ok: bool
    bonus_left: int
    message: str
    amount: int = 0
    pulse_count: int = 0


class CarOut(BaseModel):
    id: int
    plate: str
    created_at: datetime

    class Config:
        from_attributes = True


class VisitOut(BaseModel):
    id: int
    car_id: int
    created_at: datetime
    visit_no: int
    bonus_total: int
    bonus_left: int
    bonus_expired: int
    is_active_bonus: bool

    class Config:
        from_attributes = True


class StatsOut(BaseModel):
    cars_count: int
    visits_count: int
    total_bonus_paid: int
    active_bonus_count: int
