from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class PlateDetectionRequest(BaseModel):
    plate: str = Field(..., min_length=4, max_length=20)


class DisplayResponse(BaseModel):
    version: int
    text: str
    status: str
    pulse_polarity: str
    pulse_frequency_ms: int
    display_idle_text: str
    display_visit_label: str
    display_reward_label: str
    display_remaining_label: str
    display_finished_text: str
    display_currency_label: str
    test_mode: bool
    test_pulse_count: int


class BonusPressRequest(BaseModel):
    plate: str | None = None
    press_id: str | None = Field(default=None, min_length=1, max_length=64)

    @field_validator("press_id")
    @classmethod
    def press_id_is_safe(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not all(char.isalnum() or char in "-_" for char in value):
            raise ValueError("press_id may only contain letters, digits, '-' and '_'")
        return value


class TestPulseRequest(BaseModel):
    amount: int = Field(ge=1000, le=100000, multiple_of=1000)


class BonusPressResponse(BaseModel):
    ok: bool
    bonus_left: int
    message: str
    amount: int = 0
    pulse_count: int = 0
    duplicate: bool = False


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
