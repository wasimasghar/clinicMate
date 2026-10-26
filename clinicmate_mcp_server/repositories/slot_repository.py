# slot_repository.py
# Database queries for slots: free slots of a doctor and full details of one slot.

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from database.connection import get_connection

TIMEZONE = "Asia/Karachi"
DEFAULT_DAYS = 7
MAX_SLOTS = 30

# Pakistan local hours for each part of the day: (from, to)
TIME_OF_DAY_HOURS = {
    "morning": (6, 12),
    "afternoon": (12, 17),
    "evening": (17, 23),
}

# Local date/time columns, so tools never show UTC to the user
LOCAL_TIME_COLUMNS = f"""
    to_char(sl.starts_at AT TIME ZONE '{TIMEZONE}', 'YYYY-MM-DD')  AS date,
    trim(to_char(sl.starts_at AT TIME ZONE '{TIMEZONE}', 'Day'))  AS day,
    to_char(sl.starts_at AT TIME ZONE '{TIMEZONE}', 'HH12:MI AM')  AS start_time,
    to_char(sl.ends_at   AT TIME ZONE '{TIMEZONE}', 'HH12:MI AM')  AS end_time
"""


def get_available_slots(
    doctor_id: int,
    date_from: date | None = None,
    date_to: date | None = None,
    time_of_day: str | None = None,
    limit: int = 20,
) -> list[dict]:
    """Free future slots of one doctor, earliest first. Default range: next 7 days."""
    today = datetime.now(ZoneInfo(TIMEZONE)).date()
    date_from = date_from or today
    date_to = date_to or date_from + timedelta(days=DEFAULT_DAYS - 1)

    conditions = [
        "sl.doctor_id = %(doctor_id)s",
        "sl.status = 'available'",
        "sl.starts_at > now()",
        f"(sl.starts_at AT TIME ZONE '{TIMEZONE}')::date BETWEEN %(date_from)s AND %(date_to)s",
    ]
    params = {
        "doctor_id": doctor_id,
        "date_from": date_from,
        "date_to": date_to,
        "limit": min(limit, MAX_SLOTS),
    }

    if time_of_day in TIME_OF_DAY_HOURS:
        conditions.append(
            f"EXTRACT(HOUR FROM sl.starts_at AT TIME ZONE '{TIMEZONE}') >= %(hour_from)s "
            f"AND EXTRACT(HOUR FROM sl.starts_at AT TIME ZONE '{TIMEZONE}') < %(hour_to)s"
        )
        params["hour_from"], params["hour_to"] = TIME_OF_DAY_HOURS[time_of_day]

    query = f"""
        SELECT
            sl.id AS slot_id,
            {LOCAL_TIME_COLUMNS},
            c.name AS clinic,
            c.area,
            ci.name AS city
        FROM slots sl
        JOIN clinics c  ON c.id = sl.clinic_id
        JOIN cities ci  ON ci.id = c.city_id
        WHERE {" AND ".join(conditions)}
        ORDER BY sl.starts_at
        LIMIT %(limit)s
    """

    with get_connection() as conn:
        return conn.execute(query, params).fetchall()


def get_slot_details(slot_id: int) -> dict | None:
    """One slot with doctor, clinic and fee. Used to show a quote before booking."""
    query = f"""
        SELECT
            sl.id AS slot_id,
            sl.status,
            sl.starts_at > now() AS is_future,
            {LOCAL_TIME_COLUMNS},
            d.id AS doctor_id,
            d.full_name AS doctor_name,
            s.name AS specialty,
            d.consultation_fee,
            c.name AS clinic,
            c.area,
            c.address,
            ci.name AS city
        FROM slots sl
        JOIN doctors d      ON d.id = sl.doctor_id
        JOIN specialties s  ON s.id = d.specialty_id
        JOIN clinics c      ON c.id = sl.clinic_id
        JOIN cities ci      ON ci.id = c.city_id
        WHERE sl.id = %(slot_id)s
    """

    with get_connection() as conn:
        return conn.execute(query, {"slot_id": slot_id}).fetchone()