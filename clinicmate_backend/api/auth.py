# auth.py
# Login tokens: created at sign in / sign up, checked on every request to know which patient is calling.
# Token = "<patient_id>.<expiry>.<signature>"; the signature proves the backend made it, so nobody can change the id.

import hashlib
import hmac
import time

from fastapi import Depends, Header, HTTPException

from config.settings import AUTH_SECRET, TOKEN_VALID_DAYS


def sign(payload: str) -> str:
    return hmac.new(AUTH_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()


def create_token(patient_id: int) -> str:
    expires_at = int(time.time()) + TOKEN_VALID_DAYS * 24 * 60 * 60
    payload = f"{patient_id}.{expires_at}"
    return f"{payload}.{sign(payload)}"


def patient_id_from_token(token: str) -> int | None:
    """Patient id if the token is genuine and not expired, else None."""
    try:
        patient_id, expires_at, signature = token.split(".")
    except ValueError:
        return None
    if not hmac.compare_digest(signature, sign(f"{patient_id}.{expires_at}")):
        return None  # changed or fake token
    if int(expires_at) < time.time():
        return None  # expired: the app must sign in again
    return int(patient_id)


async def get_patient_id(authorization: str | None = Header(default=None)) -> int | None:
    """No Authorization header = guest (can still search doctors and ask questions).
    A wrong or expired token = 401, so the app knows to show the sign in screen."""
    if authorization is None:
        return None
    scheme, _, token = authorization.partition(" ")
    patient_id = patient_id_from_token(token) if scheme.lower() == "bearer" else None
    if patient_id is None:
        raise HTTPException(status_code=401, detail="Your login has expired. Please sign in again.")
    return patient_id


async def require_patient_id(patient_id: int | None = Depends(get_patient_id)) -> int:
    """For screens that need login (appointments, profile, waiting list): guests get 401."""
    if patient_id is None:
        raise HTTPException(status_code=401, detail="Please sign in first.")
    return patient_id
