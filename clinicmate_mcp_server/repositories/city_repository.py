# city_repository.py
# Cities and areas where ClinicMate has clinics.

from database.connection import get_connection


def list_cities() -> list[dict]:
    """All cities with their clinic areas and number of active doctors."""
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT
                ci.name,
                ci.name_urdu,
                array_agg(DISTINCT c.area ORDER BY c.area) AS areas,
                COUNT(DISTINCT ds.doctor_id) AS doctor_count
            FROM cities ci
            JOIN clinics c                ON c.city_id = ci.id
            LEFT JOIN doctor_schedules ds ON ds.clinic_id = c.id
            GROUP BY ci.id
            ORDER BY doctor_count DESC
            """
            
        ).fetchall()

def get_city_names() -> list[str]:
    """Just the city names, e.g. ['Faisalabad', 'Islamabad', 'Karachi', ...]."""
    with get_connection() as conn:
        rows = conn.execute("SELECT name FROM cities ORDER BY name").fetchall()
    return [row["name"] for row in rows]
    