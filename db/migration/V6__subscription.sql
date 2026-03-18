-- ─────────────────────────────────────────────────────────────────────────────
-- V6: Subscription gate
-- Adds trial tracking + paid subscription state to users.
-- ─────────────────────────────────────────────────────────────────────────────

ALTER TABLE users
    -- When the 30-day free trial started (set at onboarding completion)
    ADD COLUMN IF NOT EXISTS trial_started_at       TIMESTAMP,

    -- TRUE once a Razorpay payment has been confirmed
    ADD COLUMN IF NOT EXISTS is_paid                BOOLEAN   NOT NULL DEFAULT FALSE,

    -- Set to NOW() + 30 days each time a payment is confirmed;
    -- NULL means the user is still on trial or has never paid
    ADD COLUMN IF NOT EXISTS subscription_expires_at TIMESTAMP,

    -- Stores the last Razorpay payment_link_id sent to avoid creating duplicates
    ADD COLUMN IF NOT EXISTS last_payment_link_id   TEXT;

-- Fast lookup: "which users have an active subscription or active trial?"
CREATE INDEX IF NOT EXISTS idx_users_subscription
    ON users(is_paid, subscription_expires_at, trial_started_at);
