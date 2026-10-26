-- 007_add_login_fields.sql
-- Login fields for app signup: unique username, short bio, and the password hash (never the password itself).

ALTER TABLE patients
    ADD COLUMN username      TEXT UNIQUE,
    ADD COLUMN bio           TEXT,
    ADD COLUMN password_hash TEXT;