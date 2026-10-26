# get_available_slots
# slot_tools.py
# MCP tool for free appointment times of a doctor, grouped by day and clinic.

from datetime import date, datetime
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from repositories import slot_repository

PAKISTAN_TIME = ZoneInfo("Asia/Karachi")


def group_slots_by_day(slots: list[dict]) -> list[dict]:
    """Turn a flat slot list into one entry per day + clinic (smaller JSON for the LLM)."""
    groups: dict[tuple, dict] = {}
    for slot in slots:
        key = (slot["date"], slot["clinic"])
        if key not in groups:
            groups[key] = {
                "date": slot["date"],
                "day": slot["day"],
                "clinic": slot["clinic"],
                "area": slot["area"],
                "city": slot["city"],
                "times": [],
            }
        groups[key]["times"].append({"slot_id": slot["slot_id"], "time": slot["start_time"]})
    return list(groups.values())


def register_slot_tools(mcp: FastMCP) -> None:

    @mcp.tool()
    def get_available_slots(
        doctor_id: Annotated[int, Field(description="Doctor id from search_doctors")],
        date_from: Annotated[date | None, Field(description="First day to check, YYYY-MM-DD. Default: today")] = None,
        date_to: Annotated[date | None, Field(description="Last day to check, YYYY-MM-DD. Default: 7 days from date_from")] = None,
        time_of_day: Annotated[
            Literal["morning", "afternoon", "evening"] | None,
            Field(description="morning 6AM-12PM, afternoon 12-5PM, evening 5-11PM"),
        ] = None,
        limit: Annotated[int, Field(description="Maximum number of slots", ge=1, le=30)] = 15,
    ) -> dict:
        """Free appointment times of one doctor in Pakistan time, grouped by day and clinic.
        Each time has a slot_id: pass it to quote_appointment before booking.
        The result includes today's date, use it to understand 'kal' (tomorrow) or 'agle hafte' (next week)."""
        today = datetime.now(PAKISTAN_TIME)
        slots = slot_repository.get_available_slots(
            doctor_id=doctor_id,
            date_from=date_from,
            date_to=date_to,
            time_of_day=time_of_day,
            limit=limit,
        )

        result = {
            "today": today.strftime("%Y-%m-%d (%A)"),
            "doctor_id": doctor_id,
            "days": group_slots_by_day(slots),
        }
        if not slots:
            result["hint"] = "No free slots in this range. Try a later date range or another time of day, or offer join_waiting_list."
        return result