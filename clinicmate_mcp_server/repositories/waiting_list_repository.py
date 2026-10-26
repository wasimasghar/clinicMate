# waiting_list_repository.py
# Waiting list: patients wait for a fully booked doctor; the background job offers them a slot when one opens.

from datetime import date

from psycopg.errors import UniqueViolation

from database.connection import get_connection

OFFER_VALID_HOURS = 3          # an offered slot stays reserved in the list for this long
SEARCH_DAYS_WITHOUT_DATE = 7   # "any day" means within the next 7 days
MIN_HOURS_BEFORE_SLOT = 2      # never offer a slot that starts too soon to reach the clinic


class WaitingListError(Exception):
    """A waiting list rule was broken. The message is safe to show the user."""


def count_free_slots(doctor_id: int, preferred_date: date | None) -> int:
    """Free future slots of the doctor on the preferred date (or in the next 7 days)."""
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT COUNT(*) AS total FROM slots
            WHERE doctor_id = %(doctor_id)s AND status = 'available' AND starts_at > now()
              AND CASE
                    WHEN %(preferred_date)s::date IS NULL
                        THEN starts_at < now() + make_interval(days => %(days)s)
                    ELSE (starts_at AT TIME ZONE 'Asia/Karachi')::date = %(preferred_date)s::date
                  END
            """,
            {"doctor_id": doctor_id, "preferred_date": preferred_date, "days": SEARCH_DAYS_WITHOUT_DATE},
        ).fetchone()["total"]


def join(patient_id: int, doctor_id: int, preferred_date: date | None) -> dict:
    with get_connection() as conn:
        doctor = conn.execute(
            "SELECT full_name FROM doctors WHERE id = %(id)s AND is_active", {"id": doctor_id}
        ).fetchone()
        if doctor is None:
            raise WaitingListError("Doctor not found. Use a doctor id from search_doctors.")
        try:
            row = conn.execute(
                """
                INSERT INTO waiting_list (patient_id, doctor_id, preferred_date)
                VALUES (%(patient_id)s, %(doctor_id)s, %(preferred_date)s)
                RETURNING id
                """,
                {"patient_id": patient_id, "doctor_id": doctor_id, "preferred_date": preferred_date},
            ).fetchone()
        except UniqueViolation:
            raise WaitingListError(f"You are already on the waiting list for {doctor['full_name']}.")
    return {"waiting_id": row["id"], "doctor_name": doctor["full_name"], "preferred_date": preferred_date}


def list_for_patient(patient_id: int) -> list[dict]:
    """Active waiting list entries of the patient, with the offered slot if any (Pakistan time)."""
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT
                w.id AS waiting_id,
                w.status,
                d.id AS doctor_id,
                d.full_name AS doctor_name,
                to_char(w.preferred_date, 'YYYY-MM-DD') AS preferred_date,
                w.offered_slot_id,
                to_char(sl.starts_at AT TIME ZONE 'Asia/Karachi', 'Dy DD Mon, HH12:MI AM') AS offered_time,
                to_char(w.offer_expires_at AT TIME ZONE 'Asia/Karachi', 'HH12:MI AM') AS offer_expires_at
            FROM waiting_list w
            JOIN doctors d   ON d.id = w.doctor_id
            LEFT JOIN slots sl ON sl.id = w.offered_slot_id
            WHERE w.patient_id = %(patient_id)s AND w.status IN ('waiting', 'offered')
            ORDER BY w.created_at
            """,
            {"patient_id": patient_id},
        ).fetchall()


def leave(patient_id: int, waiting_id: int) -> None:
    with get_connection() as conn:
        row = conn.execute(
            """
            UPDATE waiting_list SET status = 'cancelled'
            WHERE id = %(id)s AND patient_id = %(patient_id)s AND status IN ('waiting', 'offered')
            RETURNING id
            """,
            {"id": waiting_id, "patient_id": patient_id},
        ).fetchone()
    if row is None:
        raise WaitingListError("No active waiting list entry with this id.")


def mark_booked(conn, patient_id: int, doctor_id: int) -> None:
    """Called inside the booking transaction: booking this doctor ends the patient's wait for them."""
    conn.execute(
        """
        UPDATE waiting_list SET status = 'booked'
        WHERE patient_id = %(patient_id)s AND doctor_id = %(doctor_id)s AND status IN ('waiting', 'offered')
        """,
        {"patient_id": patient_id, "doctor_id": doctor_id},
    )


def expire_old_offers() -> int:
    """Offers nobody booked in time are closed, so the slot can go to the next patient."""
    with get_connection() as conn:
        return conn.execute(
            "UPDATE waiting_list SET status = 'expired' WHERE status = 'offered' AND offer_expires_at < now()"
        ).rowcount


def make_offers() -> list[dict]:
    """First come, first served: give each waiting patient the earliest suitable free slot not offered to anyone else.
    Returns the new offers (for notifications)."""
    offers = []
    with get_connection() as conn:
        waiting = conn.execute(
            """
            SELECT w.id, w.patient_id, w.doctor_id, w.preferred_date, d.full_name AS doctor_name
            FROM waiting_list w
            JOIN doctors d ON d.id = w.doctor_id
            WHERE w.status = 'waiting'
            ORDER BY w.created_at
            FOR UPDATE OF w SKIP LOCKED
            """
        ).fetchall()

        for entry in waiting:
            slot = conn.execute(
                """
                SELECT sl.id,
                       to_char(sl.starts_at AT TIME ZONE 'Asia/Karachi', 'Dy DD Mon, HH12:MI AM') AS time,
                       c.name AS clinic
                FROM slots sl
                JOIN clinics c ON c.id = sl.clinic_id
                WHERE sl.doctor_id = %(doctor_id)s
                  AND sl.status = 'available'
                  AND sl.starts_at > now() + make_interval(hours => %(min_hours)s)
                  AND CASE
                        WHEN %(preferred_date)s::date IS NULL
                            THEN sl.starts_at < now() + make_interval(days => %(days)s)
                        ELSE (sl.starts_at AT TIME ZONE 'Asia/Karachi')::date = %(preferred_date)s::date
                      END
                  AND NOT EXISTS (
                      SELECT 1 FROM waiting_list other
                      WHERE other.offered_slot_id = sl.id AND other.status = 'offered'
                  )
                ORDER BY sl.starts_at
                LIMIT 1
                """,
                {
                    "doctor_id": entry["doctor_id"],
                    "preferred_date": entry["preferred_date"],
                    "min_hours": MIN_HOURS_BEFORE_SLOT,
                    "days": SEARCH_DAYS_WITHOUT_DATE,
                },
            ).fetchone()
            if slot is None:
                continue

            conn.execute(
                """
                UPDATE waiting_list
                SET status = 'offered', offered_slot_id = %(slot_id)s,
                    offer_expires_at = now() + make_interval(hours => %(hours)s)
                WHERE id = %(id)s
                """,
                {"slot_id": slot["id"], "hours": OFFER_VALID_HOURS, "id": entry["id"]},
            )
            offers.append({
                "patient_id": entry["patient_id"],
                "doctor_name": entry["doctor_name"],
                "slot_id": slot["id"],
                "time": slot["time"],
                "clinic": slot["clinic"],
            })
    return offers
