# generate_slots.py
# Creates bookable slots for the next 14 days from doctor_schedules. Safe to run again (skips existing slots).

from database.connection import connect_once

DAYS_AHEAD = 14
TIMEZONE = "Asia/Karachi"

GENERATE_SLOTS_SQL = """
WITH days AS (
    -- Today and the next 13 days, in Pakistan time
    SELECT (now() AT TIME ZONE %(tz)s)::date + n AS day
    FROM generate_series(0, %(days_ahead)s - 1) AS n
)
INSERT INTO slots (doctor_id, clinic_id, starts_at, ends_at)
SELECT
    s.doctor_id,
    s.clinic_id,
    slot_start AT TIME ZONE %(tz)s,
    (slot_start + make_interval(mins => s.slot_minutes)) AT TIME ZONE %(tz)s
FROM doctor_schedules AS s
JOIN days AS d
    ON EXTRACT(ISODOW FROM d.day) = s.day_of_week
CROSS JOIN LATERAL generate_series(
    d.day + s.start_time,
    d.day + s.end_time - make_interval(mins => s.slot_minutes),
    make_interval(mins => s.slot_minutes)
) AS slot_start
WHERE slot_start > now() AT TIME ZONE %(tz)s
ON CONFLICT (doctor_id, starts_at) DO NOTHING
"""


def generate_slots(days_ahead: int = DAYS_AHEAD) -> dict:
    """Returns how many new slots were created and how many future slots are free."""
    with connect_once() as conn:
        created = conn.execute(GENERATE_SLOTS_SQL, {"tz": TIMEZONE, "days_ahead": days_ahead}).rowcount
        available = conn.execute(
            "SELECT COUNT(*) AS total FROM slots WHERE status = 'available' AND starts_at > now()"
        ).fetchone()["total"]
    return {"created": created, "available": available}


if __name__ == "__main__":
    result = generate_slots()
    print(f"created    {result['created']}")
    print(f"available  {result['available']}")