-- 004_create_indexes.sql
-- Indexes for common searches (doctor filters, slots, appointments, vector search).

-- Doctor search filters: specialty, city (via clinics), fee, rating
CREATE INDEX idx_doctors_specialty   ON doctors (specialty_id) WHERE is_active;
CREATE INDEX idx_doctors_fee         ON doctors (consultation_fee);
CREATE INDEX idx_doctors_rating      ON doctors (rating DESC);
CREATE INDEX idx_clinics_city        ON clinics (city_id);
CREATE INDEX idx_schedules_clinic    ON doctor_schedules (clinic_id);

-- Free slots in a time range ("kal shaam koi slot hai?")
CREATE INDEX idx_slots_available     ON slots (doctor_id, starts_at) WHERE status = 'available';
CREATE INDEX idx_slots_starts_at     ON slots (starts_at);

-- "Meri appointments" and reminders
CREATE INDEX idx_appointments_patient ON appointments (patient_id, status);
CREATE INDEX idx_appointments_slot    ON appointments (slot_id);

-- Latest reviews of a doctor
CREATE INDEX idx_reviews_doctor      ON reviews (doctor_id, created_at DESC);

-- Waiting list jobs and device tokens
CREATE INDEX idx_waiting_doctor      ON waiting_list (doctor_id, status);
CREATE INDEX idx_device_tokens_patient ON device_tokens (patient_id);

-- RAG filter by category
CREATE INDEX idx_documents_category  ON documents (category, topic);

-- Vector search (HNSW, cosine distance)
CREATE INDEX idx_chunks_embedding
    ON chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX idx_doctors_about_embedding
    ON doctors USING hnsw (about_embedding vector_cosine_ops);
CREATE INDEX idx_doctors_review_embedding
    ON doctors USING hnsw (review_summary_embedding vector_cosine_ops);