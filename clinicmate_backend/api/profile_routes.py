# profile_routes.py
# Profile screen (login needed): GET /me to show it, PATCH /me to change name, email, city, gender or date of birth.

from fastapi import APIRouter, Depends, Request

from api.auth import require_patient_id
from api.tool_calls import call_tool
from schemas.app_schemas import Patient, ProfileUpdate

router = APIRouter(prefix="/me", tags=["profile"])


@router.get("", response_model=Patient)
async def my_profile(request: Request, patient_id: int = Depends(require_patient_id)) -> dict:
    return (await call_tool(request, "get_my_profile", {}, patient_id))["patient"]


@router.patch("", response_model=Patient)
async def update_profile(body: ProfileUpdate, request: Request, patient_id: int = Depends(require_patient_id)) -> dict:
    changes = body.model_dump(exclude_none=True, mode="json")  # only what the user changed; dates as "YYYY-MM-DD"
    return (await call_tool(request, "update_my_profile", changes, patient_id))["patient"]
