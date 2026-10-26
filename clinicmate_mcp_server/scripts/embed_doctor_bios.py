# embed_doctor_bios.py
# Embeds each doctor's "about" text (with specialty) into doctors.about_embedding, for search by the patient's problem.

from database.connection import connect_once
from services.embedding_service import embed_documents, to_vector_text


def embed_doctor_bios(redo_all: bool = False) -> int:
    """Embed bios that have no embedding yet (or all of them if redo_all). Returns how many were saved."""
    with connect_once() as conn:
        missing_only = "" if redo_all else "AND d.about_embedding IS NULL"
        doctors = conn.execute(f"""
            SELECT d.id, s.name AS specialty, d.about
            FROM doctors d
            JOIN specialties s ON s.id = d.specialty_id
            WHERE d.about IS NOT NULL {missing_only}
            ORDER BY d.id
        """).fetchall()
        if not doctors:
            return 0

        vectors = embed_documents([f"{doctor['specialty']}: {doctor['about']}" for doctor in doctors])

        with conn.cursor() as cur:
            cur.executemany(
                "UPDATE doctors SET about_embedding = %(embedding)s::vector WHERE id = %(id)s",
                [
                    {"id": doctor["id"], "embedding": to_vector_text(vector)}
                    for doctor, vector in zip(doctors, vectors)
                ],
            )
        return len(doctors)


if __name__ == "__main__":
    print(f"embedded {embed_doctor_bios()} doctor bios")