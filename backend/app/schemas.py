from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class RegisterIn(BaseModel):
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=255)
    full_name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def lower(cls, v: str) -> str:
        return v.strip().lower()


class LoginIn(BaseModel):
    email: str
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: str
    full_name: str
    role: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class StayIn(BaseModel):
    check_in: date
    check_out: date

    @model_validator(mode="after")
    def valid_dates(self):
        if self.check_out <= self.check_in:
            raise ValueError("check_out must be after check_in")
        if (self.check_out - self.check_in).days > 30:
            raise ValueError("stays are limited to 30 nights")
        return self


class ReservationIn(StayIn):
    room_type_id: int
    guests: int = Field(default=1, ge=1, le=10)


class RoomTypeAvailability(BaseModel):
    room_type_id: int
    name: str
    description: str
    capacity: int
    base_price: float
    available_rooms: int
    nights: int
    total_price: float
    points_to_earn: int


class DayAvailability(BaseModel):
    date: date
    available_rooms: int
    total_rooms: int
    nightly_price: float


class ReservationOut(BaseModel):
    id: int
    room_number: str
    room_type: str
    check_in: date
    check_out: date
    guests: int
    status: str
    total_price: float
    guest_name: str
    guest_email: str
    created_at: datetime


class LoyaltyTxOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    points: int
    reason: str
    reservation_id: int | None
    created_at: datetime


class LoyaltyOut(BaseModel):
    balance: int
    lifetime_points: int
    tier: str
    next_tier: str | None
    points_to_next_tier: int | None
    transactions: list[LoyaltyTxOut]
