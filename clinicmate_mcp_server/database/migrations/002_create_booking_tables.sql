-- 002_create_booking_tables.sql
-- Creates booking tables: doctor_schedules, slots, appointments, reviews, waiting_list, device_tokens.

-- Weekly timing of a doctor at a clinic (template used to generate slots)
CREATE TABLE doctor_schedules (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    doctor_id     BIGINT NOT NULL REFERENCES doctors(id),
    clinic_id     BIGINT NOT NULL REFERENCES clinics(id),
    day_of_week   SMALLINT NOT NULL CHECK (day_of_week BETWEEN 1 AND 7),  -- 1 = Monday, 7 = Sunday
    start_time    TIME NOT NULL,              -- 17:00
    end_time      TIME NOT NULL,              -- 21:00
    slot_minutes  SMALLINT NOT NULL DEFAULT 20,
    CHECK (end_time > start_time),
    UNIQUE (doctor_id, day_of_week, start_time)
);

-- Bookable time slots (generated from doctor_schedules)
CREATE TABLE slots (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    doctor_id   BIGINT NOT NULL REFERENCES doctors(id),
    clinic_id   BIGINT NOT NULL REFERENCES clinics(id),
    starts_at   TIMESTAMPTZ NOT NULL,
    ends_at     TIMESTAMPTZ NOT NULL,
    status      TEXT NOT NULL DEFAULT 'available'
                CHECK (status IN ('available', 'booked', 'blocked')),
    UNIQUE (doctor_id, starts_at)             -- same doctor, same time = only one slot
);

-- Patient bookings
CREATE TABLE appointments (
    id                BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    patient_id        BIGINT NOT NULL REFERENCES patients(id),
    slot_id           BIGINT NOT NULL REFERENCES slots(id),
    status            TEXT NOT NULL DEFAULT 'booked'
                      CHECK (status IN ('booked', 'cancelled', 'completed', 'no_show')),
    reason            TEXT,                   -- "skin rash for 2 weeks"
    reminder_sent_at  TIMESTAMPTZ,            -- set by background agent
    cancelled_at      TIMESTAMPTZ,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Stops double booking: one slot can have only one active booking
CREATE UNIQUE INDEX one_active_booking_per_slot
    ON appointments (slot_id)
    WHERE status = 'booked';

-- Doctor reviews
CREATE TABLE reviews (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    doctor_id       BIGINT NOT NULL REFERENCES doctors(id),
    patient_id      BIGINT REFERENCES patients(id),       -- NULL for seeded reviews
    appointment_id  BIGINT UNIQUE REFERENCES appointments(id),  -- one review per visit
    reviewer_name   TEXT NOT NULL,                        -- shown in the app
    rating          SMALLINT NOT NULL CHECK (rating BETWEEN 1 AND 5),
    comment         TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Patients waiting for a slot to open
CREATE TABLE waiting_list (
    id                BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    patient_id        BIGINT NOT NULL REFERENCES patients(id),
    doctor_id         BIGINT NOT NULL REFERENCES doctors(id),
    preferred_date    DATE,                   -- NULL = any day
    status            TEXT NOT NULL DEFAULT 'waiting'
                      CHECK (status IN ('waiting', 'offered', 'booked', 'expired', 'cancelled')),
    offered_slot_id   BIGINT REFERENCES slots(id),
    offer_expires_at  TIMESTAMPTZ,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- A patient can wait for the same doctor only once at a time
CREATE UNIQUE INDEX one_active_wait_per_doctor
    ON waiting_list (patient_id, doctor_id)
    WHERE status IN ('waiting', 'offered');

-- FCM push tokens (one patient can have many devices)
CREATE TABLE device_tokens (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    patient_id  BIGINT NOT NULL REFERENCES patients(id),
    token       TEXT NOT NULL UNIQUE,
    platform    TEXT NOT NULL CHECK (platform IN ('android', 'ios')),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);