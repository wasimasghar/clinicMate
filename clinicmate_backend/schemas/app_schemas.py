# app_schemas.py
# Response and request shapes of the app's screen APIs (doctors, appointments, waiting list, profile).
# These are the contract with the Flutter app: if an MCP tool changes, the mismatch shows up here, not as an app crash.

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

from schemas.chat_schemas import DoctorCard


# ---- Doctors ----

class Specialty(BaseModel):
    name: str
    name_urdu: str | None = None
    description: str | None = None
    doctor_count: int


class City(BaseModel):
    name: str
    name_urdu: str | None = None
    areas: list[str]
    doctor_count: int


class DoctorSummary(DoctorCard):
    """A doctor in the search list: the chat card plus gender and languages."""
    gender: str
    languages: list[str] = []


class ScheduleItem(BaseModel):
    day: str
    clinic: str
    area: str
    city: str
    address: str | None = None
    start: str
    end: str


class Review(BaseModel):
    reviewer_name: str
    rating: int
    comment: str | None = None
    date: str


class DoctorProfile(BaseModel):
    id: int
    full_name: str
    gender: str
    specialty: str
    qualifications: str | None = None
    experience_years: int
    consultation_fee: int
    rating: float
    review_count: int
    languages: list[str] = []
    about: str | None = None
    review_summary: str | None = None
    weekly_schedule: list[ScheduleItem] = []
    latest_reviews: list[Review] = []


# ---- Slots and booking ----

class SlotTime(BaseModel):
    slot_id: int
    time: str


class SlotDay(BaseModel):
    date: str
    day: str
    clinic: str
    area: str
    city: str
    times: list[SlotTime]


class SlotsResponse(BaseModel):
    today: str
    doctor_id: int
    days: list[SlotDay]


class Quote(BaseModel):
    slot_id: int
    date: str
    day: str
    start_time: str
    end_time: str
    doctor_id: int
    doctor_name: str
    specialty: str
    consultation_fee: int
    clinic: str
    area: str
    address: str | None = None
    city: str


class Appointment(BaseModel):
    appointment_id: int
    status: str  # booked, cancelled, completed, no_show
    reason: str | None = None
    date: str
    day: str
    start_time: str
    end_time: str
    is_upcoming: bool
    doctor_id: int
    doctor_name: str
    specialty: str
    consultation_fee: int
    clinic: str
    area: str
    address: str | None = None
    city: str


class BookRequest(BaseModel):
    slot_id: int
    reason: str | None = Field(default=None, max_length=300)


class RescheduleRequest(BaseModel):
    new_slot_id: int


class ReviewRequest(BaseModel):
    rating: int = Field(ge=1, le=5)
    comment: str | None = Field(default=None, max_length=500)


class ReviewResult(BaseModel):
    doctor_id: int
    doctor_name: str
    new_rating: float
    review_count: int


# ---- Waiting list ----

class WaitingListEntry(BaseModel):
    waiting_id: int
    status: str  # waiting, offered
    doctor_id: int
    doctor_name: str
    preferred_date: str | None = None
    offered_slot_id: int | None = None
    offered_time: str | None = None
    offer_expires_at: str | None = None


class WaitingListRequest(BaseModel):
    doctor_id: int
    preferred_date: date | None = None


# ---- Profile ----

class Patient(BaseModel):
    id: int
    full_name: str
    username: str | None = None
    bio: str | None = None
    phone: str
    email: str | None = None
    gender: str | None = None
    date_of_birth: str | None = None
    city: str | None = None


class ProfileUpdate(BaseModel):
    """Only the fields the user changed. Phone cannot be changed here."""
    full_name: str | None = Field(default=None, min_length=2, max_length=100)
    email: str | None = None
    city: str | None = None
    gender: Literal["male", "female", "other"] | None = None
    date_of_birth: date | None = None
