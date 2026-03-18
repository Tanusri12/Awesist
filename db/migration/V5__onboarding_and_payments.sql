-- ─────────────────────────────────────────────────────────────────────────────
-- V5: Onboarding profile columns + Payments table
-- This migration was referenced in the README but was missing.
-- Use IF NOT EXISTS on all ALTER TABLE so it is safe to re-run.
-- ─────────────────────────────────────────────────────────────────────────────

-- User profile fields set during onboarding
ALTER TABLE users
    ADD COLUMN IF NOT EXISTS business_name      TEXT,
    ADD COLUMN IF NOT EXISTS business_type      TEXT    DEFAULT 'generic',
    ADD COLUMN IF NOT EXISTS last_summary_sent_at DATE;

-- Payments: tracks total / advance / balance per order
CREATE TABLE IF NOT EXISTS payments (
    id          SERIAL PRIMARY KEY,
    user_id     TEXT        NOT NULL,
    reminder_id INTEGER     REFERENCES reminders(id) ON DELETE SET NULL,
    customer    TEXT,
    total       NUMERIC(10, 2) NOT NULL DEFAULT 0,
    advance     NUMERIC(10, 2) NOT NULL DEFAULT 0,
    status      TEXT        NOT NULL DEFAULT 'pending',   -- 'pending' | 'paid'
    paid_at     TIMESTAMP,
    created_at  TIMESTAMP   NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_payment_user
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_payments_user_status
    ON payments(user_id, status);

CREATE INDEX IF NOT EXISTS idx_payments_reminder
    ON payments(reminder_id);
