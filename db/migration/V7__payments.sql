CREATE TABLE IF NOT EXISTS payments (
    id          SERIAL PRIMARY KEY,
    reminder_id INTEGER REFERENCES reminders(id) ON DELETE CASCADE,
    user_id     TEXT NOT NULL,
    customer    TEXT,
    total       NUMERIC(10,2) DEFAULT 0,
    advance     NUMERIC(10,2) DEFAULT 0,
    status      TEXT DEFAULT 'pending',
    paid_at     TIMESTAMP,
    created_at  TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_payments_user ON payments(user_id);
CREATE INDEX IF NOT EXISTS idx_payments_reminder ON payments(reminder_id);
CREATE INDEX IF NOT EXISTS idx_payments_status ON payments(user_id, status);