# device_routes.py
# POST /devices after login (save the phone's FCM token), DELETE /devices on logout (stop notifications to it).

from fastapi import APIRouter, Depends, HTTPException, Request

from api.auth import get_patient_id
from schemas.device_schemas import DeviceTokenRequest

router = APIRouter()


def require_patient(patient_id: int | None) -> int:
    if patient_id is None:
        raise HTTPException(status_code=401, detail="Log in first.")
    return patient_id


@router.post("/devices")
async def register_device(body: DeviceTokenRequest, request: Request, patient_id: int | None = Depends(get_patient_id)) -> dict:
    result = await request.app.state.mcp.call_tool(
        "save_device_token", {"token": body.token, "platform": body.platform}, require_patient(patient_id)
    )
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return {"saved": True}


@router.delete("/devices")
async def remove_device(body: DeviceTokenRequest, request: Request, patient_id: int | None = Depends(get_patient_id)) -> dict:
    result = await request.app.state.mcp.call_tool("remove_device_token", {"token": body.token}, require_patient(patient_id))
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return {"removed": result["removed"]}
