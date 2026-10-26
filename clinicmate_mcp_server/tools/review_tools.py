# review_tools.py
# MCP tools for doctor reviews: read latest reviews and add a review after a visit.

from typing import Annotated

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from repositories import review_repository
from repositories.review_repository import ReviewError
from services import session_service
from services.session_service import NotLoggedInError


def register_review_tools(mcp: FastMCP) -> None:

    @mcp.tool()
    def get_doctor_reviews(
        doctor_id: Annotated[int, Field(description="Doctor id from search_doctors")],
        limit: Annotated[int, Field(description="How many reviews", ge=1, le=10)] = 5,
    ) -> dict:
        """Latest patient reviews of a doctor (rating 1-5, comment, date).
        get_doctor_profile already includes 3 reviews; use this only when the user wants more."""
        reviews = review_repository.get_doctor_reviews(doctor_id, limit)
        return {"doctor_id": doctor_id, "count": len(reviews), "reviews": reviews}

    @mcp.tool()
    def add_review(
        appointment_id: Annotated[int, Field(description="A past appointment from get_my_appointments(upcoming_only=False)")],
        rating: Annotated[int, Field(description="1 = very bad, 5 = excellent", ge=1, le=5)],
        comment: Annotated[str | None, Field(description="The user's own words", max_length=500)] = None,
    ) -> dict:
        """Add the logged-in patient's review for a visit that already happened. One review per appointment.
        Use the user's own rating and words; never make up a rating or comment."""
        try:
            patient_id = session_service.current_patient_id()
            result = review_repository.add_review(patient_id, appointment_id, rating, comment)
        except (NotLoggedInError, ReviewError) as error:
            return {"error": str(error)}
        return {"review_added": True, **result}