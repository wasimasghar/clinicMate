-- 001_create_core_tables.sql
-- Creates the core tables: cities, specialties, clinics, doctors, patients.

-- pgvector extension (needed for embedding columns)
CREATE EXTENSION IF NOT EXISTS vector;

-- Cities where doctors practice
CREATE TABLE cities (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE,          -- "Lahore"
    name_urdu   TEXT                           -- "لاہور"
);

-- Medical specialties
CREATE TABLE specialties (
    id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name         TEXT NOT NULL UNIQUE,         -- "Dermatologist"
    name_urdu    TEXT,                         -- "جلد کا ماہر"
    description  TEXT                          -- "Skin, hair and nail problems"
);

-- Hospitals and clinics
CREATE TABLE clinics (
    id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name       TEXT NOT NULL,                  -- "Shifa Clinic"
    city_id    BIGINT NOT NULL REFERENCES cities(id),
    area       TEXT NOT NULL,                  -- "Gulberg"
    address    TEXT,
    phone      TEXT
);

-- Doctors
CREATE TABLE doctors (
    id                        BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    full_name                 TEXT NOT NULL,
    gender                    TEXT NOT NULL CHECK (gender IN ('male', 'female')),
    specialty_id              BIGINT NOT NULL REFERENCES specialties(id),
    qualifications            TEXT,            -- "MBBS, FCPS"
    experience_years          INT NOT NULL CHECK (experience_years >= 0),
    consultation_fee          INT NOT NULL CHECK (consultation_fee > 0),  -- PKR
    languages                 TEXT[] NOT NULL DEFAULT '{English,Urdu}',
    about                     TEXT,            -- bio, used for RAG
    rating                    NUMERIC(2,1) NOT NULL DEFAULT 0,  -- 0.0 to 5.0
    review_count              INT NOT NULL DEFAULT 0,
    review_summary            TEXT,            -- written by background agent
    about_embedding           VECTOR(768),
    review_summary_embedding  VECTOR(768),
    is_active                 BOOLEAN NOT NULL DEFAULT TRUE,
    created_at                TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Patients (app users)
CREATE TABLE patients (
    id             BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    full_name      TEXT NOT NULL,
    phone          TEXT NOT NULL UNIQUE,       -- "03001234567", used for login
    email          TEXT UNIQUE,
    gender         TEXT CHECK (gender IN ('male', 'female', 'other')),
    date_of_birth  DATE,
    city_id        BIGINT REFERENCES cities(id),
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);