# auth_schemas.py
# Request and response shapes of /auth/send-otp, /auth/signup and /auth/login.

from datetime import date

from pydantic import BaseModel, Field


class SendOtpRequest(BaseModel):
    phone: str = Field(min_length=10, max_length=20)


class SignupRequest(BaseModel):
    phone: str = Field(min_length=10, max_length=20)
    username: str = Field(pattern=r"^[A-Za-z0-9_]{3,30}$")
    date_of_birth: date
    bio: str | None = Field(default=None, max_length=300)
    password: str = Field(min_length=8, max_length=128)
    otp: str = Field(min_length=4, max_length=6)


class LoginRequest(BaseModel):
    phone: str = Field(min_length=10, max_length=20)
    password: str = Field(min_length=8, max_length=128)


class AuthResponse(BaseModel):
    token: str
    expires_in_days: int
    patient: dict