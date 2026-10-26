# knowledge_repository.py
# Vector search on chunks: nearest pieces of policies or health guides for a question vector.

from database.connection import get_connection

MAX_RESULTS = 6


def search_chunks(
    query_vector_text: str,
    category: str,
    topic: str | None = None,
    limit: int = 4,
) -> list[dict]:
    """Closest chunks to the question, nearest first. distance: 0 = same meaning, 2 = opposite."""
    conditions = ["d.category = %(category)s"]
    params = {"query": query_vector_text, "category": category, "limit": min(limit, MAX_RESULTS)}
    if topic:
        conditions.append("d.topic = %(topic)s")
        params["topic"] = topic

    query = f"""
        SELECT
            d.title,
            c.heading,
            c.content,
            d.topic,
            d.source_url,
            s.name AS related_specialty,
            round((c.embedding <=> %(query)s::vector)::numeric, 3)::float AS distance
        FROM chunks c
        JOIN documents d         ON d.id = c.document_id
        LEFT JOIN specialties s  ON s.id = d.related_specialty_id
        WHERE {" AND ".join(conditions)}
        ORDER BY c.embedding <=> %(query)s::vector
        LIMIT %(limit)s
    """
    with get_connection() as conn:
        return conn.execute(query, params).fetchall()