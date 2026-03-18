CREATE TABLE conversation_memory (
    phone TEXT PRIMARY KEY,
    state JSONB,
    updated_at TIMESTAMP DEFAULT NOW()
);