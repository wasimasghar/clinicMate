# sse_events.py
# Turns agent events into Server-Sent Events text ("event: ...\ndata: ...\n\n") for POST /chat/stream.

import json

# Friendly status text the app can show while a tool runs
TOOL_STATUS = {
    "list_specialties": "Checking specialties...",
    "list_cities": "Checking cities...",
    "search_doctors": "Searching doctors...",
    "get_doctor_profile": "Opening doctor profile...",
    "get_doctor_reviews": "Reading reviews...",
    "get_available_slots": "Checking free times...",
    "quote_appointment": "Preparing booking details...",
    "book_appointment": "Booking your appointment...",
    "cancel_appointment": "Cancelling appointment...",
    "reschedule_appointment": "Rescheduling appointment...",
    "get_my_appointments": "Loading your appointments...",
    "search_policies": "Checking ClinicMate policies...",
    "search_health_guides": "Reading health guides...",
    "join_waiting_list": "Adding you to the waiting list...",
    "get_my_waiting_list": "Checking your waiting list...",
    "leave_waiting_list": "Removing you from the waiting list...",
}


def sse_event(event: str, data: dict) -> str:
    """One SSE message. The blank line at the end tells the client the message is complete."""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def token_event(text: str) -> str:
    return sse_event("token", {"text": text})


def status_event(tool_name: str) -> str:
    return sse_event("status", {"tool": tool_name, "message": TOOL_STATUS.get(tool_name, "Working on it...")})


def done_event(response: dict) -> str:
    return sse_event("done", response)


def error_event(message: str) -> str:
    return sse_event("error", {"message": message})
