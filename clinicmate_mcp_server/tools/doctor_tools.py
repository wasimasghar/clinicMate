# doctor_tools.py
# MCP tools for finding doctors: specialties, cities, search and full profile.

from datetime import datetime
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from repositories import city_repository, doctor_repository, review_repository, specialty_repository
from services.embedding_service import embed_query, to_vector_text

PAKISTAN_TIME = ZoneInfo("Asia/Karachi")
DAY_NAMES = {1: "Monday", 2: "Tuesday", 3: "Wednesday", 4: "Thursday", 5: "Friday", 6: "Saturday", 7: "Sunday"}


def format_pk_time(value: datetime | None) -> str | None:
    """UTC datetime -> 'Fri 23 Oct, 10:00 AM' in Pakistan time."""
    if value is None:
        return None
    return value.astimezone(PAKISTAN_TIME).strftime("%a %d %b, %I:%M %p")


def register_doctor_tools(mcp: FastMCP) -> None:

    @mcp.tool()
    def list_specialties() -> dict:
        """List all medical specialties with Urdu names and doctor counts.
        Call this to turn the user's words ('skin doctor', 'kaan ka doctor', 'bachon ka doctor')
        into an exact specialty name before calling search_doctors."""
        return {"specialties": specialty_repository.list_specialties()}

    @mcp.tool()
    def list_cities() -> dict:
        """List the cities and areas where ClinicMate has doctors.
        If the user's city is not in this list, tell them ClinicMate is not available there yet."""
        return {"cities": city_repository.list_cities()}

    @mcp.tool()
    def search_doctors(
        specialty: Annotated[str | None, Field(description="Exact specialty name from list_specialties, e.g. 'Dermatologist', 'ENT Specialist'")] = None,
        city: Annotated[str | None, Field(description="City name, e.g. 'Lahore'")] = None,
        area: Annotated[str | None, Field(description="Area inside the city, e.g. 'DHA', 'Gulberg', 'F-8'")] = None,
        gender: Annotated[Literal["male", "female"] | None, Field(description="Only if the user asks for a male or female doctor")] = None,
        language: Annotated[str | None, Field(description="Language the doctor speaks, e.g. 'Pashto', 'Sindhi'")] = None,
        max_fee: Annotated[int | None, Field(description="Maximum consultation fee in PKR", gt=0)] = None,
        min_rating: Annotated[float | None, Field(description="Minimum average rating, 1 to 5", ge=1, le=5)] = None,
        need: Annotated[str | None, Field(description="The patient's problem in their own words, e.g. 'skin itching after perfume'. Finds doctors whose experience matches", max_length=300)] = None,
        sort_by: Annotated[
            Literal["rating", "fee_low", "fee_high", "experience", "soonest"],
            Field(description="'soonest' = earliest free slot, 'fee_low' = cheapest first"),
        ] = "rating",
        limit: Annotated[int, Field(description="How many doctors to return", ge=1, le=10)] = 5,
    ) -> dict:
        """Find doctors by specialty, city, area, gender, language, fee and rating.
        If the user describes a problem, pass it as `need` to rank doctors whose experience matches it
        (sort_by is then ignored). Returns short doctor cards with clinics and the next free time.
        Use get_doctor_profile for details and get_available_slots for booking times."""
        # Unknown city: say clearly that ClinicMate does not serve it, and list the cities it does
        if city:
            city_names = city_repository.get_city_names()
            if city.lower() not in (name.lower() for name in city_names):
                return {
                    "count": 0,
                    "doctors": [],
                    "error": f"ClinicMate is not available in {city} yet.",
                    "available_cities": city_names,
                }
            
        doctors = doctor_repository.search_doctors(
            specialty=specialty,
            city=city,
            area=area,
            gender=gender,
            language=language,
            max_fee=max_fee,
            min_rating=min_rating,
            sort_by=sort_by,
            need_vector=to_vector_text(embed_query(need)) if need else None,
            limit=limit,
        )
        for doctor in doctors:
            doctor["next_available"] = format_pk_time(doctor.pop("next_available_at"))

        result = {"count": len(doctors), "doctors": doctors}
        if not doctors:
            result["hint"] = "No doctors matched. Try removing a filter (area, fee, gender) or try a nearby city."
        return result

    @mcp.tool()
    def get_doctor_profile(
        doctor_id: Annotated[int, Field(description="Doctor id from search_doctors")],
    ) -> dict:
        """Full profile of one doctor: qualifications, about, weekly timings at each clinic,
        review summary and the 3 latest reviews."""
        doctor = doctor_repository.get_doctor_profile(doctor_id)
        if doctor is None:
            return {"error": "Doctor not found. Use a doctor id from search_doctors."}

        for item in doctor["weekly_schedule"] or []:
            item["day"] = DAY_NAMES[item.pop("day_of_week")]
        doctor["latest_reviews"] = review_repository.get_doctor_reviews(doctor_id, limit=3)
        return doctor