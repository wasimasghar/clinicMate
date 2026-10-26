# appointment_repository.py
# Appointments: book, cancel, reschedule and list. Every write runs in one transaction.

from psycopg.errors import UniqueViolation

from database.connection import get_connection
from repositories import waiting_list_repository
from repositories.slot_repository import LOCAL_TIME_COLUMNS

MAX_APPOINTMENTS = 20


class BookingError(Exception):
    """A booking rule was broken (slot taken, appointment not found). The message is safe to show the user."""


APPOINTMENT_SELECT = f"""
    SELECT
        a.id AS appointment_id,
        a.status,
        a.reason,
        {LOCAL_TIME_COLUMNS},
        sl.starts_at > now() AS is_upcoming,
        d.id AS doctor_id,
        d.full_name AS doctor_name,
        s.name AS specialty,
        d.consultation_fee,
        c.name AS clinic,
        c.area,
        c.address,
        ci.name AS city
    FROM appointments a
    JOIN slots sl       ON sl.id = a.slot_id
    JOIN doctors d      ON d.id = sl.doctor_id
    JOIN specialties s  ON s.id = d.specialty_id
    JOIN clinics c      ON c.id = sl.clinic_id
    JOIN cities ci      ON ci.id = c.city_id
"""


def fetch_appointment(conn, appointment_id: int) -> dict:
    return conn.execute(APPOINTMENT_SELECT + " WHERE a.id = %(id)s", {"id": appointment_id}).fetchone()


def reserve_slot(conn, slot_id: int) -> None:
    """Mark a free future slot as booked. Fails if someone else booked it first."""
    row = conn.execute(
        """
        UPDATE slots SET status = 'booked'
        WHERE id = %(slot_id)s AND status = 'available' AND starts_at > now()
        RETURNING id
        """,
        {"slot_id": slot_id},
    ).fetchone()
    if row is None:
        raise BookingError("This slot is no longer available. Please choose another time.")


def release_slot(conn, slot_id: int) -> None:
    conn.execute("UPDATE slots SET status = 'available' WHERE id = %(slot_id)s", {"slot_id": slot_id})


def book_appointment(patient_id: int, slot_id: int, reason: str | None = None) -> dict:
    with get_connection() as conn:
        reserve_slot(conn, slot_id)
        try:
            appointment_id = conn.execute(
                """
                INSERT INTO appointments (patient_id, slot_id, reason)
                VALUES (%(patient_id)s, %(slot_id)s, %(reason)s)
                RETURNING id
                """,
                {"patient_id": patient_id, "slot_id": slot_id, "reason": reason},
            ).fetchone()["id"]
        except UniqueViolation:
            # Safety net: the partial unique index caught a second active booking
            raise BookingError("This slot is no longer available. Please choose another time.")
        appointment = fetch_appointment(conn, appointment_id)
        waiting_list_repository.mark_booked(conn, patient_id, appointment["doctor_id"])
        return appointment


def cancel_appointment(patient_id: int, appointment_id: int) -> dict:
    with get_connection() as conn:
        row = conn.execute(
            """
            UPDATE appointments AS a
            SET status = 'cancelled', cancelled_at = now()
            FROM slots AS sl
            WHERE a.id = %(appointment_id)s
              AND a.patient_id = %(patient_id)s
              AND a.status = 'booked'
              AND sl.id = a.slot_id
              AND sl.starts_at > now()
            RETURNING a.slot_id
            """,
            {"appointment_id": appointment_id, "patient_id": patient_id},
        ).fetchone()
        if row is None:
            raise BookingError("No upcoming booked appointment found with this id.")

        release_slot(conn, row["slot_id"])
        return fetch_appointment(conn, appointment_id)


def reschedule_appointment(patient_id: int, appointment_id: int, new_slot_id: int) -> dict:
    """Move a booked appointment to another free slot of the same doctor."""
    with get_connection() as conn:
        current = conn.execute(
            """
            SELECT a.slot_id, sl.doctor_id
            FROM appointments a
            JOIN slots sl ON sl.id = a.slot_id
            WHERE a.id = %(appointment_id)s
              AND a.patient_id = %(patient_id)s
              AND a.status = 'booked'
              AND sl.starts_at > now()
            FOR UPDATE OF a
            """,
            {"appointment_id": appointment_id, "patient_id": patient_id},
        ).fetchone()
        if current is None:
            raise BookingError("No upcoming booked appointment found with this id.")

        new_slot = conn.execute(
            "SELECT doctor_id FROM slots WHERE id = %(slot_id)s", {"slot_id": new_slot_id}
        ).fetchone()
        if new_slot is None or new_slot["doctor_id"] != current["doctor_id"]:
            raise BookingError("You can only reschedule to another slot of the same doctor.")

        reserve_slot(conn, new_slot_id)
        conn.execute(
            """
            UPDATE appointments
            SET slot_id = %(new_slot_id)s, reminder_sent_at = NULL
            WHERE id = %(appointment_id)s
            """,
            {"new_slot_id": new_slot_id, "appointment_id": appointment_id},
        )
        release_slot(conn, current["slot_id"])
        return fetch_appointment(conn, appointment_id)


def get_patient_appointments(patient_id: int, upcoming_only: bool = True) -> list[dict]:
    """Upcoming booked appointments (soonest first), or full history (latest first)."""
    if upcoming_only:
        filters = "AND a.status = 'booked' AND sl.starts_at > now() ORDER BY sl.starts_at ASC"
    else:
        filters = "ORDER BY sl.starts_at DESC"

    query = APPOINTMENT_SELECT + f" WHERE a.patient_id = %(patient_id)s {filters} LIMIT {MAX_APPOINTMENTS}"
    with get_connection() as conn:
        return conn.execute(query, {"patient_id": patient_id}).fetchall()


def get_appointment(patient_id: int, appointment_id: int) -> dict | None:
    """One appointment, only if it belongs to this patient."""
    query = APPOINTMENT_SELECT + " WHERE a.id = %(appointment_id)s AND a.patient_id = %(patient_id)s"
    with get_connection() as conn:
        return conn.execute(query, {"appointment_id": appointment_id, "patient_id": patient_id}).fetchone()

# ---- Background job queries (called only through job_tools, never by the chat LLM) ----

def complete_past_appointments() -> int:
    """Booked appointments whose time is over become 'completed' (then the patient can review them)."""
    with get_connection() as conn:
        return conn.execute(
            """
            UPDATE appointments AS a SET status = 'completed'
            FROM slots AS sl
            WHERE sl.id = a.slot_id AND a.status = 'booked' AND sl.ends_at < now()
            """
        ).rowcount


def get_due_reminders(hours_ahead: int = 24) -> list[dict]:
    """Booked appointments starting within the next hours that have not been reminded yet."""
    # Same columns as APPOINTMENT_SELECT plus patient_id, which the notification needs
    query = APPOINTMENT_SELECT.replace("SELECT", "SELECT a.patient_id,", 1) + """
        WHERE a.status = 'booked'
          AND a.reminder_sent_at IS NULL
          AND sl.starts_at > now()
          AND sl.starts_at < now() + make_interval(hours => %(hours)s)
        ORDER BY sl.starts_at
    """
    with get_connection() as conn:
        return conn.execute(query, {"hours": hours_ahead}).fetchall()


def mark_reminders_sent(appointment_ids: list[int]) -> int:
    with get_connection() as conn:
        return conn.execute(
            "UPDATE appointments SET reminder_sent_at = now() WHERE id = ANY(%(ids)s) AND reminder_sent_at IS NULL",
            {"ids": appointment_ids},
        ).rowcount
