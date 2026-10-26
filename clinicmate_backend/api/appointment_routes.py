# appointment_routes.py
# "My Appointments" screens (login needed): list, book after a quote, cancel, reschedule, review a past visit.

from fastapi import APIRouter, Depends, Request

from api.auth import require_patient_id
from api.tool_calls import call_tool
from schemas.app_schemas import Appointment, BookRequest, RescheduleRequest, ReviewRequest, ReviewResult

router = APIRouter(prefix="/appointments", tags=["appointments"])


@router.get("", response_model=list[Appointment])
async def my_appointments(request: Request, upcoming_only: bool = True, patient_id: int = Depends(require_patient_id)) -> list[dict]:
    result = await call_tool(request, "get_my_appointments", {"upcoming_only": upcoming_only}, patient_id)
    return result["appointments"]


@router.post("", response_model=Appointment, status_code=201)
async def book(body: BookRequest, request: Request, patient_id: int = Depends(require_patient_id)) -> dict:
    """Book a slot. The app must first show GET /slots/{slot_id}/quote and the user must tap Confirm."""
    result = await call_tool(request, "book_appointment", {"slot_id": body.slot_id, "reason": body.reason}, patient_id)
    return result["appointment"]


@router.post("/{appointment_id}/cancel", response_model=Appointment)
async def cancel(appointment_id: int, request: Request, patient_id: int = Depends(require_patient_id)) -> dict:
    result = await call_tool(request, "cancel_appointment", {"appointment_id": appointment_id}, patient_id)
    return result["appointment"]


@router.post("/{appointment_id}/reschedule", response_model=Appointment)
async def reschedule(appointment_id: int, body: RescheduleRequest, request: Request, patient_id: int = Depends(require_patient_id)) -> dict:
    """Move to another slot of the same doctor. Quote the new slot first (GET /slots/{new_slot_id}/quote)."""
    result = await call_tool(
        request, "reschedule_appointment", {"appointment_id": appointment_id, "new_slot_id": body.new_slot_id}, patient_id
    )
    return result["appointment"]


@router.post("/{appointment_id}/review", response_model=ReviewResult, status_code=201)
async def review(appointment_id: int, body: ReviewRequest, request: Request, patient_id: int = Depends(require_patient_id)) -> dict:
    return await call_tool(
        request, "add_review", {"appointment_id": appointment_id, "rating": body.rating, "comment": body.comment}, patient_id
    )
