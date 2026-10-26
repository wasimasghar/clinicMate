# quote / book / cancel / reschedule / my appointments
# appointment_tools.py
# MCP tools for appointments: quote -> user says yes -> book, plus cancel, reschedule and list.

from typing import Annotated

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from repositories import appointment_repository, slot_repository
from repositories.appointment_repository import BookingError
from services import session_service
from services.session_service import NotLoggedInError


def register_appointment_tools(mcp: FastMCP) -> None:

    @mcp.tool()
    def quote_appointment(
        slot_id: Annotated[int, Field(description="slot_id from get_available_slots")],
    ) -> dict:
        """Show booking details (doctor, clinic, address, date, time, fee) for a slot BEFORE booking.
        Always call this first, show the quote to the user and wait for a clear yes.
        book_appointment only works for a slot quoted in the last 10 minutes."""
        slot = slot_repository.get_slot_details(slot_id)
        if slot is None:
            return {"error": "Slot not found. Use a slot_id from get_available_slots."}
        if slot["status"] != "available" or not slot["is_future"]:
            return {"error": "This slot is no longer available. Please choose another time."}

        session_service.remember_quote(slot_id)
        quote = {key: value for key, value in slot.items() if key not in ("status", "is_future")}
        return {
            "quote": quote,
            "logged_in": session_service.is_logged_in(),
            "next_step": "Show this quote and ask the user to confirm. If not logged in, ask for their phone number first.",
        }

    @mcp.tool()
    def book_appointment(
        slot_id: Annotated[int, Field(description="The same slot_id that was quoted")],
        reason: Annotated[str | None, Field(description="Short reason in the user's words, e.g. 'skin rash for 2 weeks'", max_length=300)] = None,
    ) -> dict:
        """Book the quoted slot for the logged-in patient.
        Call ONLY after quote_appointment and after the user clearly said yes."""
        try:
            patient_id = session_service.current_patient_id()
            if not session_service.has_valid_quote(slot_id):
                return {"error": "Call quote_appointment for this slot and get the user's confirmation first."}
            appointment = appointment_repository.book_appointment(patient_id, slot_id, reason)
        except (NotLoggedInError, BookingError) as error:
            return {"error": str(error)}

        session_service.clear_quote(slot_id)
        return {"booked": True, "appointment": appointment}

    @mcp.tool()
    def cancel_appointment(
        appointment_id: Annotated[int, Field(description="appointment_id from get_my_appointments")],
    ) -> dict:
        """Cancel an upcoming appointment of the logged-in patient.
        Show which appointment will be cancelled and get a clear yes before calling.
        The slot becomes free for other patients."""
        try:
            patient_id = session_service.current_patient_id()
            appointment = appointment_repository.cancel_appointment(patient_id, appointment_id)
        except (NotLoggedInError, BookingError) as error:
            return {"error": str(error)}
        return {"cancelled": True, "appointment": appointment}

    @mcp.tool()
    def reschedule_appointment(
        appointment_id: Annotated[int, Field(description="appointment_id from get_my_appointments")],
        new_slot_id: Annotated[int, Field(description="New slot_id of the SAME doctor, already quoted")],
    ) -> dict:
        """Move an upcoming appointment to another free slot of the same doctor.
        First get new times with get_available_slots, quote the new slot with quote_appointment,
        and get a clear yes from the user."""
        try:
            patient_id = session_service.current_patient_id()
            if not session_service.has_valid_quote(new_slot_id):
                return {"error": "Call quote_appointment for the new slot and get the user's confirmation first."}
            appointment = appointment_repository.reschedule_appointment(patient_id, appointment_id, new_slot_id)
        except (NotLoggedInError, BookingError) as error:
            return {"error": str(error)}

        session_service.clear_quote(new_slot_id)
        return {"rescheduled": True, "appointment": appointment}

    @mcp.tool()
    def get_my_appointments(
        upcoming_only: Annotated[bool, Field(description="True = upcoming booked visits, False = full history")] = True,
    ) -> dict:
        """Appointments of the logged-in patient with doctor, clinic, date, time and status."""
        try:
            patient_id = session_service.current_patient_id()
        except NotLoggedInError as error:
            return {"error": str(error)}

        appointments = appointment_repository.get_patient_appointments(patient_id, upcoming_only)
        return {"count": len(appointments), "appointments": appointments}