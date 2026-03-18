-- Add business profile to users
ALTER TABLE users
ADD COLUMN IF NOT EXISTS business_name TEXT,
ADD COLUMN IF NOT EXISTS business_type TEXT DEFAULT 'generic';

-- Persistent conversation state (replaces in-memory dict)
CREATE TABLE IF NOT EXISTS conversation_memory (
    phone      TEXT PRIMARY KEY,
    state      JSONB     NOT NULL,
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_conversation_updated
ON conversation_memory(updated_at);