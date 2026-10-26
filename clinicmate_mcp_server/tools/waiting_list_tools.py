# waiting_list_tools.py
# MCP tools for the waiting list: join when a doctor is fully booked, see your entries and offers, leave.

from datetime import date
from typing import Annotated

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from repositories import waiting_list_repository
from repositories.waiting_list_repository import WaitingListError
from services import session_service
from services.session_service import NotLoggedInError


def register_waiting_list_tools(mcp: FastMCP) -> None:

    @mcp.tool()
    def join_waiting_list(
        doctor_id: Annotated[int, Field(description="Doctor id from search_doctors")],
        preferred_date: Annotated[date | None, Field(description="YYYY-MM-DD, or leave empty for any day in the next 7 days")] = None,
    ) -> dict:
        """Put the logged-in patient on a doctor's waiting list when no free slot suits them.
        When a slot opens, the patient gets a notification and the offer appears in get_my_waiting_list.
        Only works if the doctor has no free slots for that date; otherwise book directly."""
        try:
            patient_id = session_service.current_patient_id()
            free = waiting_list_repository.count_free_slots(doctor_id, preferred_date)
            if free:
                return {
                    "error": f"This doctor still has {free} free slots for that time. Show them with get_available_slots and book directly.",
                }
            entry = waiting_list_repository.join(patient_id, doctor_id, preferred_date)
        except (NotLoggedInError, WaitingListError) as error:
            return {"error": str(error)}
        return {"joined": True, **entry, "next_step": "Tell the user they will be notified when a slot opens."}

    @mcp.tool()
    def get_my_waiting_list() -> dict:
        """The logged-in patient's active waiting list entries. status 'offered' means a slot was found:
        show offered_time, and if the user wants it, quote_appointment with offered_slot_id and book after a yes."""
        try:
            patient_id = session_service.current_patient_id()
        except NotLoggedInError as error:
            return {"error": str(error)}
        entries = waiting_list_repository.list_for_patient(patient_id)
        return {"count": len(entries), "entries": entries}

    @mcp.tool()
    def leave_waiting_list(
        waiting_id: Annotated[int, Field(description="waiting_id from get_my_waiting_list")],
    ) -> dict:
        """Remove the logged-in patient from a waiting list."""
        try:
            waiting_list_repository.leave(session_service.current_patient_id(), waiting_id)
        except (NotLoggedInError, WaitingListError) as error:
            return {"error": str(error)}
        return {"left": True}
