
import re

from psycopg.errors import UniqueViolation

from database.connection import get_connection

# Only these columns can be changed by update_patient
UPDATABLE_FIELDS = {"full_name", "email", "gender", "date_of_birth"}

PATIENT_SELECT = """
    SELECT
        p.id,
        p.full_name,
        p.username,
        p.bio,
        p.phone,
        p.email,
        p.gender,
        to_char(p.date_of_birth, 'YYYY-MM-DD') AS date_of_birth,
        ci.name AS city
    FROM patients p
    LEFT JOIN cities ci ON ci.id = p.city_id
"""


class PatientError(Exception):
    """Invalid patient data (bad phone, duplicate number). The message is safe to show the user."""


def normalize_phone(phone: str) -> str:
    """'+92 300-0000001', '0092300...' or '0300 0000001' -> '03000000001'."""
    digits = re.sub(r"\D", "", phone)
    if digits.startswith("0092"):
        digits = "0" + digits[4:]
    elif digits.startswith("92"):
        digits = "0" + digits[2:]

    if not re.fullmatch(r"03\d{9}", digits):
        raise PatientError("Please enter a valid Pakistani mobile number like 03001234567.")
    return digits


def get_patient_by_phone(phone: str) -> dict | None:
    with get_connection() as conn:
        return conn.execute(
            PATIENT_SELECT + " WHERE p.phone = %(phone)s", {"phone": normalize_phone(phone)}
        ).fetchone()


def get_patient(patient_id: int) -> dict | None:
    with get_connection() as conn:
        return conn.execute(PATIENT_SELECT + " WHERE p.id = %(id)s", {"id": patient_id}).fetchone()


def create_patient(
    full_name: str,
    phone: str,
    city: str | None = None,
    gender: str | None = None,
    email: str | None = None,
) -> dict:
    params = {
        "full_name": full_name.strip(),
        "phone": normalize_phone(phone),
        "city": city,
        "gender": gender.lower() if gender else None,
        "email": email,
    }
    with get_connection() as conn:
        try:
            patient_id = conn.execute(
                """
                INSERT INTO patients (full_name, phone, city_id, gender, email)
                VALUES (
                    %(full_name)s,
                    %(phone)s,
                    (SELECT id FROM cities WHERE name ILIKE %(city)s),
                    %(gender)s,
                    %(email)s
                )
                RETURNING id
                """,
                params,
            ).fetchone()["id"]
        except UniqueViolation:
            raise PatientError("This phone number or email is already registered. Please log in instead.")
        return conn.execute(PATIENT_SELECT + " WHERE p.id = %(id)s", {"id": patient_id}).fetchone()


def update_patient(patient_id: int, city: str | None = None, **fields) -> dict:
    """Update only the given fields. Unknown field names are ignored."""
    changes = {key: value for key, value in fields.items() if key in UPDATABLE_FIELDS and value is not None}

    set_parts = [f"{column} = %({column})s" for column in changes]
    if city:
        set_parts.append("city_id = (SELECT id FROM cities WHERE name ILIKE %(city)s)")
        changes["city"] = city
    if not set_parts:
        raise PatientError("Nothing to update.")

    changes["id"] = patient_id
    with get_connection() as conn:
        try:
            conn.execute(f"UPDATE patients SET {', '.join(set_parts)} WHERE id = %(id)s", changes)
        except UniqueViolation:
            raise PatientError("This email is already used by another account.")
        return conn.execute(PATIENT_SELECT + " WHERE p.id = %(id)s", {"id": patient_id}).fetchone()

def create_account(phone: str, username: str, date_of_birth, bio: str | None, password_hash: str) -> dict:
    """App signup. full_name starts as the username; the patient can change it later."""
    params = {
        "phone": normalize_phone(phone),
        "username": username.strip(),
        "date_of_birth": date_of_birth,
        "bio": bio,
        "password_hash": password_hash,
    }
    with get_connection() as conn:
        try:
            patient_id = conn.execute(
                """
                INSERT INTO patients (full_name, username, phone, date_of_birth, bio, password_hash)
                VALUES (%(username)s, %(username)s, %(phone)s, %(date_of_birth)s, %(bio)s, %(password_hash)s)
                RETURNING id
                """,
                params,
            ).fetchone()["id"]
        except UniqueViolation:
            raise PatientError("This phone number or username is already registered. Please sign in instead.")
        return conn.execute(PATIENT_SELECT + " WHERE p.id = %(id)s", {"id": patient_id}).fetchone()


def get_login(phone: str) -> dict | None:
    """id and password hash for a phone number (used only to check a login)."""
    with get_connection() as conn:
        return conn.execute(
            "SELECT id, password_hash FROM patients WHERE phone = %(phone)s",
            {"phone": normalize_phone(phone)},
        ).fetchone()

    