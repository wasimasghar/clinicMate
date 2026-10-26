# chat_repository.py
# Saved chat messages: store one turn (question + answer) and read the latest messages of a conversation.

from database.connection import get_connection

MAX_MESSAGES = 30


def save_turn(patient_id: int, conversation_id: str, user_text: str, assistant_text: str) -> None:
    """Save the user's message and the assistant's reply together (one transaction)."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.executemany(
                """
                INSERT INTO chat_messages (patient_id, conversation_id, role, content)
                VALUES (%(patient_id)s, %(conversation_id)s, %(role)s, %(content)s)
                """,
                [
                    {"patient_id": patient_id, "conversation_id": conversation_id, "role": "user", "content": user_text},
                    {"patient_id": patient_id, "conversation_id": conversation_id, "role": "assistant", "content": assistant_text},
                ],
            )


def get_recent_messages(patient_id: int, conversation_id: str, limit: int = 20) -> list[dict]:
    """Latest messages of this patient's conversation, oldest first (the order the LLM reads them)."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT role, content
            FROM chat_messages
            WHERE patient_id = %(patient_id)s AND conversation_id = %(conversation_id)s
            ORDER BY created_at DESC, id DESC
            LIMIT %(limit)s
            """,
            {"patient_id": patient_id, "conversation_id": conversation_id, "limit": min(limit, MAX_MESSAGES)},
        ).fetchall()
    return list(reversed(rows))
