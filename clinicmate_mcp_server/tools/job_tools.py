# job_tools.py
# Backend-only MCP tools for the background agent: daily housekeeping, waiting list offers and reminders.
# They refuse to run for single-user clients (Claude Desktop), and the backend hides them from the chat LLM.

from typing import Annotated

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from database.seed.generate_slots import generate_slots
from repositories import appointment_repository, review_repository, waiting_list_repository
from services import session_service
from services.embedding_service import embed_documents, to_vector_text

BACKEND_ONLY_ERROR = {"error": "This tool is only for the ClinicMate backend."}


def register_job_tools(mcp: FastMCP) -> None:

    @mcp.tool()
    def run_scheduled_jobs(
        reminder_hours_ahead: Annotated[int, Field(ge=1, le=72)] = 24,
    ) -> dict:
        """BACKEND ONLY: run housekeeping (new slots, completed visits, expired offers), make waiting list offers,
        and return the reminders and offers the backend should send as notifications."""
        if session_service.chat_login_allowed():
            return BACKEND_ONLY_ERROR

        slots = generate_slots()
        completed = appointment_repository.complete_past_appointments()
        expired = waiting_list_repository.expire_old_offers()
        offers = waiting_list_repository.make_offers()
        reminders = appointment_repository.get_due_reminders(reminder_hours_ahead)
        return {
            "summary": {
                "slots_created": slots["created"],
                "appointments_completed": completed,
                "offers_expired": expired,
                "offers_made": len(offers),
                "reminders_due": len(reminders),
            },
            "offers": offers,
            "reminders": reminders,
        }

    @mcp.tool()
    def mark_reminders_sent(
        appointment_ids: Annotated[list[int], Field(description="Appointments whose reminder was delivered")],
    ) -> dict:
        """BACKEND ONLY: remember that these reminders were sent, so they are not sent twice."""
        if session_service.chat_login_allowed():
            return BACKEND_ONLY_ERROR
        return {"marked": appointment_repository.mark_reminders_sent(appointment_ids)}

    @mcp.tool()
    def get_doctors_needing_review_summary(
        limit: Annotated[int, Field(ge=1, le=20)] = 5,
    ) -> dict:
        """BACKEND ONLY: doctors whose review summary is missing or a week old with new reviews, with their latest reviews."""
        if session_service.chat_login_allowed():
            return BACKEND_ONLY_ERROR
        return {"doctors": review_repository.get_doctors_needing_summary(limit)}

    @mcp.tool()
    def save_review_summary(
        doctor_id: int,
        summary: Annotated[str, Field(min_length=20, max_length=1000)],
    ) -> dict:
        """BACKEND ONLY: store a doctor's review summary and its embedding (used for search and the profile)."""
        if session_service.chat_login_allowed():
            return BACKEND_ONLY_ERROR
        embedding = to_vector_text(embed_documents([summary])[0])
        review_repository.save_review_summary(doctor_id, summary, embedding)
        return {"saved": True}
