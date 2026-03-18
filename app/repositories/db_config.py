import os
from urllib.parse import urlparse

DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL:
    parsed = urlparse(DATABASE_URL)
    DB_CONFIG = {
        "host":     parsed.hostname,
        "database": parsed.path.lstrip("/"),
        "user":     parsed.username,
        "password": parsed.password,
        "port":     parsed.port or 5432,
        "sslmode":  "require" if "supabase" in (parsed.hostname or "") or "neon" in (parsed.hostname or "") else "prefer"
    }
else:
    DB_CONFIG = {
        "host":     os.getenv("DB_HOST",     "localhost"),
        "database": os.getenv("DB_NAME",     "wassist"),
        "user":     os.getenv("DB_USER",     "postgres"),
        "password": os.getenv("DB_PASSWORD", "postgres"),
        "port":     int(os.getenv("DB_PORT", 5432)),
        "sslmode":  "prefer"
    }