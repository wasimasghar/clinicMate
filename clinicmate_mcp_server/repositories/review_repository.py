# review_repository.py
# Reviews: read a doctor's reviews and let a patient review a past visit (updates doctor rating).

from psycopg.errors import UniqueViolation

from database.connection import get_connection

MAX_REVIEWS = 10


class ReviewError(Exception):
    """A review rule was broken. The message is safe to show the user."""


def get_doctor_reviews(doctor_id: int, limit: int = 5) -> list[dict]:
    """Latest reviews of a doctor."""
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT
                reviewer_name,
                rating,
                comment,
                to_char(created_at AT TIME ZONE 'Asia/Karachi', 'DD Mon YYYY') AS date
            FROM reviews
            WHERE doctor_id = %(doctor_id)s
            ORDER BY created_at DESC
            LIMIT %(limit)s
            """,
            {"doctor_id": doctor_id, "limit": min(limit, MAX_REVIEWS)},
        ).fetchall()


def add_review(patient_id: int, appointment_id: int, rating: int, comment: str | None = None) -> dict:
    """Patient reviews their own past visit. One review per appointment."""
    if not 1 <= rating <= 5:
        raise ReviewError("Rating must be between 1 and 5.")

    with get_connection() as conn:
        # The visit must belong to this patient and must already have happened
        visit = conn.execute(
            """
            SELECT
                sl.doctor_id,
                split_part(p.full_name, ' ', 1) || ' ' || left(split_part(p.full_name, ' ', 2), 1) || '.' AS reviewer_name
            FROM appointments a
            JOIN slots sl    ON sl.id = a.slot_id
            JOIN patients p  ON p.id = a.patient_id
            WHERE a.id = %(appointment_id)s
              AND a.patient_id = %(patient_id)s
              AND (a.status = 'completed' OR (a.status = 'booked' AND sl.starts_at < now()))
            """,
            {"appointment_id": appointment_id, "patient_id": patient_id},
        ).fetchone()
        if visit is None:
            raise ReviewError("You can only review your own appointment after the visit.")

        try:
            conn.execute(
                """
                INSERT INTO reviews (doctor_id, patient_id, appointment_id, reviewer_name, rating, comment)
                VALUES (%(doctor_id)s, %(patient_id)s, %(appointment_id)s, %(reviewer_name)s, %(rating)s, %(comment)s)
                """,
                {
                    "doctor_id": visit["doctor_id"],
                    "patient_id": patient_id,
                    "appointment_id": appointment_id,
                    "reviewer_name": visit["reviewer_name"],
                    "rating": rating,
                    "comment": comment,
                },
            )
        except UniqueViolation:
            raise ReviewError("You have already reviewed this appointment.")

        # Refresh the doctor's average rating and count in the same transaction
        return conn.execute(
            """
            UPDATE doctors AS d
            SET rating = stats.avg_rating, review_count = stats.total
            FROM (
                SELECT ROUND(AVG(rating), 1) AS avg_rating, COUNT(*) AS total
                FROM reviews
                WHERE doctor_id = %(doctor_id)s
            ) AS stats
            WHERE d.id = %(doctor_id)s
            RETURNING d.id AS doctor_id, d.full_name AS doctor_name, d.rating::float AS new_rating, d.review_count
            """,
            {"doctor_id": visit["doctor_id"]},
        ).fetchone()

# ---- Weekly review summaries (background job only) ----

SUMMARY_REFRESH_DAYS = 7     # redo a summary at most once a week, and only if new reviews came in
REVIEWS_PER_SUMMARY = 40     # latest reviews the LLM reads for one summary


def get_doctors_needing_summary(limit: int) -> list[dict]:
    """Doctors with reviews and no summary yet, or new reviews since a summary older than a week.
    Each comes with its latest reviews for the LLM to read."""
    with get_connection() as conn:
        doctors = conn.execute(
            """
            SELECT d.id AS doctor_id, d.full_name AS doctor_name, s.name AS specialty,
                   d.rating::float AS rating, d.review_count
            FROM doctors d
            JOIN specialties s ON s.id = d.specialty_id
            WHERE d.is_active AND d.review_count > 0
              AND (
                  d.review_summary_updated_at IS NULL
                  OR (
                      d.review_summary_updated_at < now() - make_interval(days => %(days)s)
                      AND EXISTS (
                          SELECT 1 FROM reviews r
                          WHERE r.doctor_id = d.id AND r.created_at > d.review_summary_updated_at
                      )
                  )
              )
            ORDER BY d.review_summary_updated_at NULLS FIRST, d.id
            LIMIT %(limit)s
            """,
            {"days": SUMMARY_REFRESH_DAYS, "limit": limit},
        ).fetchall()

        for doctor in doctors:
            doctor["reviews"] = conn.execute(
                """
                SELECT rating, comment FROM reviews
                WHERE doctor_id = %(doctor_id)s AND comment IS NOT NULL
                ORDER BY created_at DESC
                LIMIT %(limit)s
                """,
                {"doctor_id": doctor["doctor_id"], "limit": REVIEWS_PER_SUMMARY},
            ).fetchall()
    return doctors


def save_review_summary(doctor_id: int, summary: str, embedding_text: str) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE doctors
            SET review_summary = %(summary)s,
                review_summary_embedding = %(embedding)s::vector,
                review_summary_updated_at = now()
            WHERE id = %(doctor_id)s
            """,
            {"summary": summary, "embedding": embedding_text, "doctor_id": doctor_id},
        )
