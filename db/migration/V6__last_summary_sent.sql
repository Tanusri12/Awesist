ALTER TABLE users
ADD COLUMN IF NOT EXISTS last_summary_sent_at DATE;