-- Proper booking status model
-- Replaces the ambiguous 'completed' with distinct statuses.
--
-- Status lifecycle:
--   pending     → Active booking, reminder not yet fired
--   processing  → Worker has picked it up to fire the reminder (transient)
--   notified    → Reminder WhatsApp sent to vendor
--   delivered   → Vendor marked done via 'done #N'
--   cancelled   → Vendor deleted the booking (soft delete)

-- Migrate existing 'completed' rows — treat as delivered (best approximation)
UPDATE reminders SET status = 'delivered' WHERE status = 'completed';

-- Drop old constraint if any and add the proper one
ALTER TABLE reminders DROP CONSTRAINT IF EXISTS reminders_status_check;
ALTER TABLE reminders ADD CONSTRAINT reminders_status_check
    CHECK (status IN ('pending', 'processing', 'notified', 'delivered', 'cancelled'));

-- Add cancelled_at for audit trail
ALTER TABLE reminders ADD COLUMN IF NOT EXISTS cancelled_at TIMESTAMPTZ;
