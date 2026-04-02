-- Security migration — run once on the server
-- psql -U your_user -d your_db -f migrate_security.sql

-- 1. DB-backed AI rate limits (replaces in-memory dict)
CREATE TABLE IF NOT EXISTS ai_rate_limits (
    user_id  TEXT        NOT NULL,
    date     DATE        NOT NULL,
    count    INTEGER     NOT NULL DEFAULT 0,
    last_ts  FLOAT       NOT NULL DEFAULT 0,
    PRIMARY KEY (user_id, date)
);

-- 2. AI call audit log (already used in code, create if missing)
CREATE TABLE IF NOT EXISTS ai_call_logs (
    id         SERIAL      PRIMARY KEY,
    user_id    TEXT        NOT NULL,
    message    TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_ai_call_logs_user ON ai_call_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_ai_call_logs_ts   ON ai_call_logs(created_at);

-- Done
SELECT 'Migration complete' AS status;
