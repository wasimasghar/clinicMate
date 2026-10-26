# session_service.py
# Which patient the current tool call is for: sent by the trusted backend with each call,
# or logged in through chat (single-user clients like Claude Desktop and Inspector).

import os
from datetime import datetime, timedelta

from mcp.server.lowlevel.server import request_ctx

# The backend starts this server with TRUST_CLIENT_PATIENT_ID=true and sends the verified patient id
# in every tool call's _meta. Claude Desktop and Inspector do not set it, so they use chat login instead.
TRUST_CLIENT_PATIENT_ID = os.getenv("TRUST_CLIENT_PATIENT_ID") == "true"
QUOTE_VALID_FOR = timedelta(minutes=10)

_chat_login_patient_id: int | None = None  # used only by single-user clients
_quoted_slots: dict[tuple[int | None, int], datetime] = {}  # (patient_id or None, slot_id) -> when quoted


class NotLoggedInError(Exception):
    """Raised when a tool needs a patient but nobody is logged in."""


def chat_login_allowed() -> bool:
    """Login and register tools work only for single-user clients; app users log in inside the app."""
    return not TRUST_CLIENT_PATIENT_ID


def patient_id_from_client() -> int | None:
    """patient_id from the current tool call's _meta, sent by the backend."""
    try:
        meta = request_ctx.get().meta
    except LookupError:  # not inside a tool call (e.g. a script)
        return None
    value = (meta.model_extra or {}).get("patient_id") if meta else None
    return int(value) if value is not None else None


def optional_patient_id() -> int | None:
    """The patient for this call, or None if nobody is logged in."""
    if TRUST_CLIENT_PATIENT_ID:
        return patient_id_from_client()
    return _chat_login_patient_id


def current_patient_id() -> int:
    """The patient for this call. Raises if nobody is logged in."""
    patient_id = optional_patient_id()
    if patient_id is None:
        if TRUST_CLIENT_PATIENT_ID:
            raise NotLoggedInError("Please log in to the ClinicMate app first.")
        raise NotLoggedInError("Please log in first with your phone number.")
    return patient_id


def is_logged_in() -> bool:
    return optional_patient_id() is not None


def login(patient_id: int) -> None:
    global _chat_login_patient_id
    _chat_login_patient_id = patient_id


def logout() -> None:
    global _chat_login_patient_id
    _chat_login_patient_id = None
    _quoted_slots.clear()


def remember_quote(slot_id: int) -> None:
    _quoted_slots[(optional_patient_id(), slot_id)] = datetime.now()


def has_valid_quote(slot_id: int) -> bool:
    """True if this patient (or a not-yet-logged-in user who then logged in) saw this slot's quote in the last 10 minutes."""
    now = datetime.now()
    for key in ((optional_patient_id(), slot_id), (None, slot_id)):
        quoted_at = _quoted_slots.get(key)
        if quoted_at is not None and now - quoted_at < QUOTE_VALID_FOR:
            return True
    return False


def clear_quote(slot_id: int) -> None:
    _quoted_slots.pop((optional_patient_id(), slot_id), None)
    _quoted_slots.pop((None, slot_id), None)
