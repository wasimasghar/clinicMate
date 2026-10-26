# waiting_list_routes.py
# Waiting list screens (login needed): see entries and offers, join for a fully booked doctor, leave.

from fastapi import APIRouter, Depends, Request

from api.auth import require_patient_id
from api.tool_calls import call_tool, without_none
from schemas.app_schemas import WaitingListEntry, WaitingListRequest

router = APIRouter(prefix="/waiting-list", tags=["waiting list"])


@router.get("", response_model=list[WaitingListEntry])
async def my_waiting_list(request: Request, patient_id: int = Depends(require_patient_id)) -> list[dict]:
    return (await call_tool(request, "get_my_waiting_list", {}, patient_id))["entries"]


@router.post("", status_code=201)
async def join(body: WaitingListRequest, request: Request, patient_id: int = Depends(require_patient_id)) -> dict:
    arguments = without_none(
        doctor_id=body.doctor_id,
        preferred_date=body.preferred_date.isoformat() if body.preferred_date else None,
    )
    result = await call_tool(request, "join_waiting_list", arguments, patient_id)
    return {"waiting_id": result["waiting_id"], "doctor_name": result["doctor_name"]}


@router.delete("/{waiting_id}")
async def leave(waiting_id: int, request: Request, patient_id: int = Depends(require_patient_id)) -> dict:
    await call_tool(request, "leave_waiting_list", {"waiting_id": waiting_id}, patient_id)
    return {"left": True}
