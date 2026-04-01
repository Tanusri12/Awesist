CREATE TABLE IF NOT EXISTS ai_call_logs (
    id         SERIAL PRIMARY KEY,
    user_id    TEXT NOT NULL,
    message    TEXT NOT NULL,
    called_at  TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
