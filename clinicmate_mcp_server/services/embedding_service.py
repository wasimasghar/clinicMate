# Gemini embeddings for queries
# embedding_service.py
# Turns text into 768-number vectors with Gemini (gemini-embedding-001). Same model for documents and queries.

import time

from google import genai
from google.genai import errors, types

from config.settings import GEMINI_API_KEY

EMBEDDING_MODEL = "gemini-embedding-001"
EMBEDDING_DIMENSIONS = 768        # must match VECTOR(768) in the database
BATCH_SIZE = 50                   # texts per API call
PAUSE_BETWEEN_BATCHES = 2         # seconds, to stay inside the free-tier rate limit
RATE_LIMIT_WAIT = 60              # seconds to wait after a 429 (free tier: 100 embeddings per minute)
MAX_RETRIES = 3

_client = genai.Client(api_key=GEMINI_API_KEY)


def embed_batch(batch: list[str], task_type: str, wait_on_limit: bool):
    """One API call. On a rate-limit error (429) wait a minute and try again, if allowed."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return _client.models.embed_content(
                model=EMBEDDING_MODEL,
                contents=batch,
                config=types.EmbedContentConfig(task_type=task_type, output_dimensionality=EMBEDDING_DIMENSIONS),
            )
        except errors.ClientError as error:
            if error.code != 429 or not wait_on_limit or attempt == MAX_RETRIES:
                raise
            time.sleep(RATE_LIMIT_WAIT)


def embed_texts(texts: list[str], task_type: str, wait_on_limit: bool = False) -> list[list[float]]:
    """Embed many texts in batches. Returns one vector per text, in the same order."""
    vectors: list[list[float]] = []
    for start in range(0, len(texts), BATCH_SIZE):
        response = embed_batch(texts[start:start + BATCH_SIZE], task_type, wait_on_limit)
        vectors.extend(embedding.values for embedding in response.embeddings)
        if start + BATCH_SIZE < len(texts):
            time.sleep(PAUSE_BETWEEN_BATCHES)
    return vectors


def embed_documents(texts: list[str]) -> list[list[float]]:
    """For chunks, doctor bios and review summaries (stored in the database). Waits on rate limits."""
    return embed_texts(texts, "RETRIEVAL_DOCUMENT", wait_on_limit=True)


def embed_query(text: str) -> list[float]:
    """For the user's search question. Fails fast on rate limits (a chat should not wait a minute)."""
    return embed_texts([text], "RETRIEVAL_QUERY")[0]


def to_vector_text(vector: list[float]) -> str:
    """Python list -> '[0.1,0.2,...]', the text form pgvector understands."""
    return "[" + ",".join(str(number) for number in vector) + "]"