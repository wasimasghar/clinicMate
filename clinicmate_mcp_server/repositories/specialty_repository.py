# specialty_repository.py
# Medical specialties with doctor counts, so the LLM can pick an exact specialty name.

from database.connection import get_connection


def list_specialties() -> list[dict]:
    """All specialties with Urdu name, short description and number of active doctors."""
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT
                s.name,
                s.name_urdu,
                s.description,
                COUNT(d.id) AS doctor_count
            FROM specialties s
            LEFT JOIN doctors d ON d.specialty_id = s.id AND d.is_active
            GROUP BY s.id
            ORDER BY s.name
            """
        ).fetchall()