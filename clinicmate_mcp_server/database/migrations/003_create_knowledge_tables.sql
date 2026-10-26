-- 003_create_knowledge_tables.sql
-- Creates RAG tables: documents (one row per .md file) and chunks (pieces with embeddings).

-- One row per knowledge_base file
CREATE TABLE documents (
    id                    BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    title                 TEXT NOT NULL,          -- "Hearing Loss"
    category              TEXT NOT NULL CHECK (category IN ('policy', 'health_guide')),
    topic                 TEXT,                   -- "ent", "allergy", "heart" (NULL for policies)
    source_file           TEXT NOT NULL UNIQUE,   -- "health_guides/ent/hearing_loss.md"
    source_url            TEXT,                   -- WHO / NIH link shown as source
    related_specialty_id  BIGINT REFERENCES specialties(id),  -- to suggest doctors
    content_hash          TEXT NOT NULL,          -- skip re-embedding if file unchanged
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Small pieces of each document, used for vector search
CREATE TABLE chunks (
    id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    document_id  BIGINT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index  INT NOT NULL,                    -- 0, 1, 2 ... order inside the document
    heading      TEXT,                            -- "Types of hearing aids"
    content      TEXT NOT NULL,
    embedding    VECTOR(768) NOT NULL,
    UNIQUE (document_id, chunk_index)
);