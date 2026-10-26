# device_token_repository.py
# FCM device tokens: one patient can have many phones; a token always belongs to the phone's current patient.

from database.connection import get_connection


def save_token(patient_id: int, token: str, platform: str) -> None:
    """Add or move a token. If another patient logged in on this phone before, the token now belongs to this one."""
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO device_tokens (patient_id, token, platform)
            VALUES (%(patient_id)s, %(token)s, %(platform)s)
            ON CONFLICT (token) DO UPDATE
                SET patient_id = EXCLUDED.patient_id, platform = EXCLUDED.platform, updated_at = now()
            """,
            {"patient_id": patient_id, "token": token, "platform": platform},
        )


def remove_patient_token(patient_id: int, token: str) -> int:
    """On logout: stop sending this patient's notifications to this phone."""
    with get_connection() as conn:
        return conn.execute(
            "DELETE FROM device_tokens WHERE patient_id = %(patient_id)s AND token = %(token)s",
            {"patient_id": patient_id, "token": token},
        ).rowcount


def remove_tokens(tokens: list[str]) -> int:
    """Tokens FCM says are dead (app uninstalled)."""
    with get_connection() as conn:
        return conn.execute("DELETE FROM device_tokens WHERE token = ANY(%(tokens)s)", {"tokens": tokens}).rowcount


def get_tokens(patient_ids: list[int]) -> list[dict]:
    with get_connection() as conn:
        return conn.execute(
            "SELECT patient_id, token FROM device_tokens WHERE patient_id = ANY(%(ids)s)",
            {"ids": patient_ids},
        ).fetchall()
