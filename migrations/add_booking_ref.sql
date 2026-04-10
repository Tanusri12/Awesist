-- Add booking_ref to reminders table
-- Each vendor gets their own sequential counter: #1, #2, #3 ...
-- These never change or reuse even if orders are deleted.

ALTER TABLE reminders ADD COLUMN IF NOT EXISTS booking_ref INTEGER;

-- Backfill existing rows with sequential per-vendor numbers ordered by creation
WITH ranked AS (
    SELECT id, ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY id) AS rn
    FROM reminders
)
UPDATE reminders r SET booking_ref = ranked.rn
FROM ranked WHERE r.id = ranked.id;

-- Unique per vendor
CREATE UNIQUE INDEX IF NOT EXISTS reminders_user_booking_ref_idx ON reminders (user_id, booking_ref);
