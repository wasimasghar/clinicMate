# chunk + embed + save knowledge_base files
# ingest_knowledge_base.py
# Reads knowledge_base/*.md, splits them into chunks by ## heading, embeds them and saves to documents + chunks.

import hashlib
from pathlib import Path

from database.connection import connect_once
from services.embedding_service import embed_documents, to_vector_text
KNOWLEDGE_DIR = Path(__file__).parent.parent / "knowledge_base"
MAX_CHUNK_CHARS = 1500   # long sections are split by paragraph below this size
MIN_CHUNK_CHARS = 40     # tiny pieces carry no meaning, skip them


def read_markdown(path: Path) -> tuple[dict, str] | None:
    """Split a file into (header fields, body). None if the file has no --- header yet."""
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return None
    _, header, body = text.split("---", 2)

    meta = {}
    for line in header.strip().splitlines():
        key, _, value = line.partition(":")
        meta[key.strip()] = value.strip() or None
    return meta, body.strip()


def split_long_text(text: str) -> list[str]:
    """Split by paragraphs so that every piece stays under MAX_CHUNK_CHARS."""
    pieces, current = [], ""
    for paragraph in text.split("\n\n"):
        if current and len(current) + len(paragraph) > MAX_CHUNK_CHARS:
            pieces.append(current.strip())
            current = ""
        current += paragraph + "\n\n"
    if current.strip():
        pieces.append(current.strip())
    return pieces


def split_into_chunks(title: str, body: str) -> list[dict]:
    """One chunk per ## section: {"heading": "Title > Section", "content": "..."}."""
    chunks = []
    for section in body.split("\n## ")[1:]:  # [0] is the "# Title" part before the first ##
        heading, _, section_text = section.partition("\n")
        for piece in split_long_text(section_text.strip()):
            if len(piece) >= MIN_CHUNK_CHARS:
                chunks.append({"heading": f"{title} > {heading.strip()}", "content": piece})
    return chunks

def ingest_file(conn, path: Path) -> str:
    parsed = read_markdown(path)
    if parsed is None:
        return "skip (no header yet)"
    meta, body = parsed

    source_file = path.relative_to(KNOWLEDGE_DIR).as_posix()
    content_hash = hashlib.sha256(path.read_bytes()).hexdigest()

    existing = conn.execute(
        "SELECT content_hash FROM documents WHERE source_file = %(source_file)s",
        {"source_file": source_file},
    ).fetchone()
    if existing and existing["content_hash"] == content_hash:
        return "unchanged"

    chunks = split_into_chunks(meta["title"], body)
    if not chunks:
        return "skip (no ## sections)"

    # Embed heading + content together, so the vector knows the topic of the piece
    vectors = embed_documents([f"{chunk['heading']}\n{chunk['content']}" for chunk in chunks])

    with conn.transaction():
        document_id = conn.execute(
            """
            INSERT INTO documents (title, category, topic, source_file, source_url, related_specialty_id, content_hash)
            VALUES (
                %(title)s, %(category)s, %(topic)s, %(source_file)s, %(source_url)s,
                (SELECT id FROM specialties WHERE name = %(specialty)s),
                %(content_hash)s
            )
            ON CONFLICT (source_file) DO UPDATE SET
                title = EXCLUDED.title,
                category = EXCLUDED.category,
                topic = EXCLUDED.topic,
                source_url = EXCLUDED.source_url,
                related_specialty_id = EXCLUDED.related_specialty_id,
                content_hash = EXCLUDED.content_hash,
                updated_at = now()
            RETURNING id
            """,
            {
                "title": meta["title"],
                "category": meta["category"],
                "topic": meta.get("topic"),
                "source_file": source_file,
                "source_url": meta.get("source_url"),
                "specialty": meta.get("specialty"),
                "content_hash": content_hash,
            },
        ).fetchone()["id"]

        # Replace old chunks of this document with the new ones
        conn.execute("DELETE FROM chunks WHERE document_id = %(id)s", {"id": document_id})
        with conn.cursor() as cur:
            cur.executemany(
                """
                INSERT INTO chunks (document_id, chunk_index, heading, content, embedding)
                VALUES (%(document_id)s, %(chunk_index)s, %(heading)s, %(content)s, %(embedding)s::vector)
                """,
                [
                    {
                        "document_id": document_id,
                        "chunk_index": index,
                        "heading": chunk["heading"],
                        "content": chunk["content"],
                        "embedding": to_vector_text(vector),
                    }
                    for index, (chunk, vector) in enumerate(zip(chunks, vectors))
                ],
            )
    return f"saved {len(chunks)} chunks"


def remove_deleted_files(conn, current_files: list[str]) -> int:
    """Delete documents whose .md file no longer exists (their chunks go too, ON DELETE CASCADE)."""
    return conn.execute(
        "DELETE FROM documents WHERE NOT (source_file = ANY(%(files)s))",
        {"files": current_files},
    ).rowcount


def ingest_knowledge_base() -> None:
    paths = sorted(KNOWLEDGE_DIR.rglob("*.md"))
    with connect_once() as conn:
        for path in paths:
            status = ingest_file(conn, path)
            conn.commit()  # save each file right away, so a later error does not undo it
            print(f"{status:<22} {path.relative_to(KNOWLEDGE_DIR)}")

        removed = remove_deleted_files(conn, [path.relative_to(KNOWLEDGE_DIR).as_posix() for path in paths])
        if removed:
            print(f"removed {removed} deleted documents")


if __name__ == "__main__":
    ingest_knowledge_base()