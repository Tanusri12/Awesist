-- Add columns used by the reminder worker for tracking sent status and retries
ALTER TABLE reminders ADD COLUMN IF NOT EXISTS sent_at TIMESTAMP;
ALTER TABLE reminders ADD COLUMN IF NOT EXISTS retry_count INTEGER DEFAULT 0;
ALTER TABLE reminders ADD COLUMN IF NOT EXISTS last_attempt TIMESTAMP;
