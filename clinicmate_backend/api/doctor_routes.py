# doctor_routes.py
# Public screens (no login needed): specialties, cities, doctor search, doctor profile, reviews, free slots, booking quote.

from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request

from api.auth import get_patient_id
from api.tool_calls import call_tool, without_none
from schemas.app_schemas import City, DoctorProfile, DoctorSummary, Quote, Review, SlotsResponse, Specialty

router = APIRouter(tags=["doctors"])


@router.get("/specialties", response_model=list[Specialty])
async def list_specialties(request: Request) -> list[dict]:
    return (await call_tool(request, "list_specialties", {}))["specialties"]


@router.get("/cities", response_model=list[City])
async def list_cities(request: Request) -> list[dict]:
    return (await call_tool(request, "list_cities", {}))["cities"]


@router.get("/doctors", response_model=list[DoctorSummary])
async def search_doctors(
    request: Request,
    specialty: str | None = None,
    city: str | None = None,
    area: str | None = None,
    gender: Literal["male", "female"] | None = None,
    language: str | None = None,
    max_fee: int | None = Query(default=None, gt=0),
    min_rating: float | None = Query(default=None, ge=1, le=5),
    need: str | None = Query(default=None, max_length=300, description="Patient's problem in their words"),
    sort_by: Literal["rating", "fee_low", "fee_high", "experience", "soonest"] = "rating",
    limit: int = Query(default=10, ge=1, le=10),
) -> list[dict]:
    arguments = without_none(
        specialty=specialty, city=city, area=area, gender=gender, language=language,
        max_fee=max_fee, min_rating=min_rating, need=need, sort_by=sort_by, limit=limit,
    )
    return (await call_tool(request, "search_doctors", arguments))["doctors"]


@router.get("/doctors/{doctor_id}", response_model=DoctorProfile)
async def get_doctor(doctor_id: int, request: Request) -> dict:
    return await call_tool(request, "get_doctor_profile", {"doctor_id": doctor_id})


@router.get("/doctors/{doctor_id}/reviews", response_model=list[Review])
async def get_doctor_reviews(doctor_id: int, request: Request, limit: int = Query(default=10, ge=1, le=10)) -> list[dict]:
    return (await call_tool(request, "get_doctor_reviews", {"doctor_id": doctor_id, "limit": limit}))["reviews"]


@router.get("/doctors/{doctor_id}/slots", response_model=SlotsResponse)
async def get_doctor_slots(
    doctor_id: int,
    request: Request,
    date_from: date | None = None,
    date_to: date | None = None,
    time_of_day: Literal["morning", "afternoon", "evening"] | None = None,
    limit: int = Query(default=30, ge=1, le=30),
) -> dict:
    arguments = without_none(
        doctor_id=doctor_id,
        date_from=date_from.isoformat() if date_from else None,
        date_to=date_to.isoformat() if date_to else None,
        time_of_day=time_of_day,
        limit=limit,
    )
    return await call_tool(request, "get_available_slots", arguments)


@router.get("/slots/{slot_id}/quote", response_model=Quote)
async def quote_slot(slot_id: int, request: Request, patient_id: int | None = Depends(get_patient_id)) -> dict:
    """Booking summary for the confirm screen. POST /appointments works only after this (within 10 minutes)."""
    return (await call_tool(request, "quote_appointment", {"slot_id": slot_id}, patient_id))["quote"]
