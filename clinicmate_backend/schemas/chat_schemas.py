# chat_schemas.py
# Request and response shapes of POST /chat (what the Flutter app sends and receives).

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    conversation_id: str = Field(min_length=1, max_length=100, description="Same id for every message of one chat")
    message: str = Field(min_length=1, max_length=2000)


class ClinicInfo(BaseModel):
    clinic: str
    area: str
    city: str


class DoctorCard(BaseModel):
    id: int
    full_name: str
    specialty: str
    qualifications: str | None = None
    experience_years: int
    consultation_fee: int
    rating: float
    review_count: int
    clinics: list[ClinicInfo] = []
    next_available: str | None = None


class BookingCard(BaseModel):
    """A quote waiting for the user's yes, or a booked / cancelled appointment."""
    kind: str  # "quote", "booked", "cancelled", "rescheduled"
    slot_id: int | None = None
    appointment_id: int | None = None
    doctor_name: str
    specialty: str
    clinic: str
    area: str
    city: str
    date: str
    day: str
    start_time: str
    consultation_fee: int


class SourceInfo(BaseModel):
    title: str
    section: str
    url: str | None = None


class ChatResponse(BaseModel):
    conversation_id: str
    reply: str
    doctor_cards: list[DoctorCard] = []
    booking_card: BookingCard | None = None
    sources: list[SourceInfo] = []
    show_disclaimer: bool = False