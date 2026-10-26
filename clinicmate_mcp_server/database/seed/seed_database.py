# seed_database.py
# Fills Supabase with seed data from data/*.json (cities, specialties, clinics, doctors, schedules, patients, reviews).

import json
from pathlib import Path

from database.connection import connect_once

DATA_DIR = Path(__file__).parent / "data"

# Emptied before every seed run. Cities and specialties are not here: they are upserted,
# because RAG documents point to specialties and must not be deleted.
TABLES_TO_RESET = [
    "device_tokens", "waiting_list", "reviews", "appointments",
    "slots", "doctor_schedules", "patients", "doctors", "clinics",
]


def load_json(file_name: str) -> list[dict]:
    return json.loads((DATA_DIR / file_name).read_text(encoding="utf-8"))


def id_map(conn, table: str, key_column: str) -> dict[str, int]:
    """Name -> id for a table, e.g. {"Lahore": 1, "Karachi": 2}."""
    rows = conn.execute(f"SELECT id, {key_column} FROM {table}").fetchall()
    return {row[key_column]: row["id"] for row in rows}


def reset_tables(conn) -> None:
    conn.execute(f"TRUNCATE {', '.join(TABLES_TO_RESET)} RESTART IDENTITY")


def seed_cities(conn) -> None:
    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO cities (name, name_urdu)
            VALUES (%(name)s, %(name_urdu)s)
            ON CONFLICT (name) DO UPDATE SET name_urdu = EXCLUDED.name_urdu
            """,
            load_json("cities.json"),
        )


def seed_specialties(conn) -> None:
    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO specialties (name, name_urdu, description)
            VALUES (%(name)s, %(name_urdu)s, %(description)s)
            ON CONFLICT (name) DO UPDATE
                SET name_urdu = EXCLUDED.name_urdu, description = EXCLUDED.description
            """,
            load_json("specialties.json"),
        )


def seed_clinics(conn) -> None:
    city_ids = id_map(conn, "cities", "name")
    rows = [{**clinic, "city_id": city_ids[clinic["city"]]} for clinic in load_json("clinics.json")]
    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO clinics (name, city_id, area, address, phone)
            VALUES (%(name)s, %(city_id)s, %(area)s, %(address)s, %(phone)s)
            """,
            rows,
        )


def seed_doctors(conn, doctors: list[dict]) -> None:
    specialty_ids = id_map(conn, "specialties", "name")
    rows = [{**doctor, "specialty_id": specialty_ids[doctor["specialty"]]} for doctor in doctors]
    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO doctors (full_name, gender, specialty_id, qualifications,
                                 experience_years, consultation_fee, languages, about)
            VALUES (%(full_name)s, %(gender)s, %(specialty_id)s, %(qualifications)s,
                    %(experience_years)s, %(consultation_fee)s, %(languages)s, %(about)s)
            """,
            rows,
        )


def seed_doctor_schedules(conn, doctors: list[dict]) -> None:
    doctor_ids = id_map(conn, "doctors", "full_name")
    clinic_ids = id_map(conn, "clinics", "name")

    # One row per doctor + clinic + day ("days": [1, 3, 5] becomes 3 rows)
    rows = []
    for doctor in doctors:
        for schedule in doctor["schedules"]:
            for day in schedule["days"]:
                rows.append({
                    "doctor_id": doctor_ids[doctor["full_name"]],
                    "clinic_id": clinic_ids[schedule["clinic"]],
                    "day_of_week": day,
                    "start_time": schedule["start"],
                    "end_time": schedule["end"],
                    "slot_minutes": schedule["slot_minutes"],
                })

    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO doctor_schedules (doctor_id, clinic_id, day_of_week,
                                          start_time, end_time, slot_minutes)
            VALUES (%(doctor_id)s, %(clinic_id)s, %(day_of_week)s,
                    %(start_time)s, %(end_time)s, %(slot_minutes)s)
            """,
            rows,
        )


def seed_patients(conn) -> None:
    city_ids = id_map(conn, "cities", "name")
    rows = [{**patient, "city_id": city_ids[patient["city"]]} for patient in load_json("patients.json")]
    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO patients (full_name, phone, email, gender, date_of_birth, city_id)
            VALUES (%(full_name)s, %(phone)s, %(email)s, %(gender)s, %(date_of_birth)s, %(city_id)s)
            """,
            rows,
        )


def seed_reviews(conn) -> None:
    doctor_ids = id_map(conn, "doctors", "full_name")
    rows = [{**review, "doctor_id": doctor_ids[review["doctor"]]} for review in load_json("reviews.json")]
    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO reviews (doctor_id, reviewer_name, rating, comment, created_at)
            VALUES (%(doctor_id)s, %(reviewer_name)s, %(rating)s, %(comment)s, %(created_at)s)
            """,
            rows,
        )


def update_doctor_ratings(conn) -> None:
    """Average rating and review count per doctor, calculated from the reviews table."""
    conn.execute("""
        UPDATE doctors AS d
        SET rating = stats.avg_rating, review_count = stats.total
        FROM (
            SELECT doctor_id, ROUND(AVG(rating), 1) AS avg_rating, COUNT(*) AS total
            FROM reviews
            GROUP BY doctor_id
        ) AS stats
        WHERE d.id = stats.doctor_id
    """)


def print_counts(conn) -> None:
    for table in ["cities", "specialties", "clinics", "doctors", "doctor_schedules", "patients", "reviews"]:
        count = conn.execute(f"SELECT COUNT(*) AS total FROM {table}").fetchone()["total"]
        print(f"{table:<18} {count}")


def seed_database() -> None:
    doctors = load_json("doctors.json")

    # One transaction: if any step fails, nothing is saved
    with connect_once() as conn:
        reset_tables(conn)
        seed_cities(conn)
        seed_specialties(conn)
        seed_clinics(conn)
        seed_doctors(conn, doctors)
        seed_doctor_schedules(conn, doctors)
        seed_patients(conn)
        seed_reviews(conn)
        update_doctor_ratings(conn)
        print_counts(conn)


if __name__ == "__main__":
    seed_database()