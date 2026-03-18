-- Users table

CREATE TABLE users (
    id TEXT PRIMARY KEY,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE reminders (
    id SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    task TEXT NOT NULL,
    reminder_time TIMESTAMP NOT NULL,
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT NOW(),
    CONSTRAINT fk_user
        FOREIGN KEY(user_id)
        REFERENCES users(id)
        ON DELETE CASCADE
);

CREATE TABLE user_activity (

    id SERIAL PRIMARY KEY,

    user_id INTEGER NOT NULL,

    message_count INTEGER DEFAULT 0,

    window_start TIMESTAMP DEFAULT NOW(),

    CONSTRAINT fk_user_activity
        FOREIGN KEY(user_id)
        REFERENCES users(id)
        ON DELETE CASCADE
);


CREATE TABLE job_logs (
    id SERIAL PRIMARY KEY,
    job_name TEXT NOT NULL,
    run_date DATE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'SUCCESS'
);