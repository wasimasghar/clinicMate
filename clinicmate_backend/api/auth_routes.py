# auth_routes.py
# POST /auth/send-otp, /auth/signup, /auth/login. Signup needs the OTP (development: always DEV_OTP).

import hmac

from fastapi import APIRouter, HTTPException, Request

from api.auth import create_token
from config.settings import DEV_OTP, TOKEN_VALID_DAYS
from schemas.auth_schemas import AuthResponse, LoginRequest, SendOtpRequest, SignupRequest

router = APIRouter(prefix="/auth")


@router.post("/send-otp")
async def send_otp(body: SendOtpRequest) -> dict:
    """Development: no SMS is sent, the code is always DEV_OTP. A real SMS service goes here later."""
    return {"sent": True, "message": "Development mode: no SMS sent. Use the test OTP."}


@router.post("/signup", response_model=AuthResponse)
async def signup(body: SignupRequest, request: Request) -> AuthResponse:
    if not hmac.compare_digest(body.otp, DEV_OTP):
        raise HTTPException(status_code=400, detail="Wrong OTP.")

    result = await request.app.state.mcp.call_tool(
        "create_account",
        {
            "phone": body.phone,
            "username": body.username,
            "date_of_birth": body.date_of_birth.isoformat(),
            "bio": body.bio,
            "password": body.password,
        },
    )
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    patient = result["patient"]
    return AuthResponse(token=create_token(patient["id"]), expires_in_days=TOKEN_VALID_DAYS, patient=patient)


@router.post("/login", response_model=AuthResponse)
async def login(body: LoginRequest, request: Request) -> AuthResponse:
    result = await request.app.state.mcp.call_tool("verify_login", {"phone": body.phone, "password": body.password})
    if "error" in result:
        raise HTTPException(status_code=401, detail=result["error"])

    patient = result["patient"]
    return AuthResponse(token=create_token(patient["id"]), expires_in_days=TOKEN_VALID_DAYS, patient=patient)