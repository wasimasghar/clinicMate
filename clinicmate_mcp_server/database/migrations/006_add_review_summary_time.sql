-- 006_add_review_summary_time.sql
-- When each doctor's review summary was last written, so the weekly job only redoes doctors with new reviews.

ALTER TABLE doctors ADD COLUMN review_summary_updated_at TIMESTAMPTZ;
