-- 005_create_chat_tables.sql
-- Saved chat messages of logged-in patients, so a conversation survives a backend restart.

CREATE TABLE chat_messages (
    id               BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    patient_id       BIGINT NOT NULL REFERENCES patients(id),
    conversation_id  TEXT NOT NULL,                -- id chosen by the app for one chat screen
    role             TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content          TEXT NOT NULL,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Latest messages of one patient's conversation
CREATE INDEX idx_chat_messages_conversation
    ON chat_messages (patient_id, conversation_id, created_at DESC);
