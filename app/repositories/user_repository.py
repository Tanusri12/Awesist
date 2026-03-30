from datetime import datetime, timedelta

from repositories.db_pool import get_connection, release_connection


def get_or_create_user(phone: str):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO users (id) VALUES (%s) ON CONFLICT DO NOTHING",
            (phone,)
        )
        conn.commit()
        cursor.execute(
            """
            SELECT id, business_name, business_type, last_summary_sent_at,
                   trial_started_at, is_paid, subscription_expires_at
            FROM users WHERE id = %s
            """,
            (phone,)
        )
        row = cursor.fetchone()
        return {
            "id":                      row[0],
            "business_name":           row[1],
            "business_type":           row[2] or "generic",
            "last_summary_sent_at":    row[3],
            "trial_started_at":        row[4],
            "is_paid":                 row[5] or False,
            "subscription_expires_at": row[6],
        }
    finally:
        cursor.close()
        release_connection(conn)


def update_user_profile(phone: str, business_name: str, business_type: str):
    """Set business profile and stamp trial_started_at at onboarding completion."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE users
            SET business_name    = %s,
                business_type    = %s,
                trial_started_at = COALESCE(trial_started_at, NOW())
            WHERE id = %s
            """,
            (business_name, business_type, phone)
        )
        conn.commit()
    finally:
        cursor.close()
        release_connection(conn)


def is_onboarded(phone: str) -> bool:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT business_name FROM users WHERE id = %s",
            (phone,)
        )
        row = cursor.fetchone()
        return bool(row and row[0])
    finally:
        cursor.close()
        release_connection(conn)


# ─────────────────────────────────────────────────────────────────────────────
# Subscription helpers
# ─────────────────────────────────────────────────────────────────────────────

def get_subscription_status(phone: str):
    """
    Returns a dict:
      - status: 'trial' | 'active' | 'expired'
      - trial_days_left: int  (only meaningful when status == 'trial')
      - expires_at: datetime | None
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT trial_started_at, is_paid, subscription_expires_at
            FROM users WHERE id = %s
            """,
            (phone,)
        )
        row = cursor.fetchone()
        if not row:
            return {"status": "expired", "trial_days_left": 0, "expires_at": None}

        trial_started_at, is_paid, subscription_expires_at = row
        now = datetime.utcnow()

        # Paid subscription still active
        if is_paid and subscription_expires_at and subscription_expires_at > now:
            return {
                "status":          "active",
                "trial_days_left": 0,
                "expires_at":      subscription_expires_at,
            }

        # Within the free trial window
        if trial_started_at:
            from config import TRIAL_DAYS
            trial_end = trial_started_at + timedelta(days=TRIAL_DAYS)
            if now < trial_end:
                days_left = max(1, (trial_end - now).days)
                return {
                    "status":          "trial",
                    "trial_days_left": days_left,
                    "expires_at":      trial_end,
                }

        # Trial over, no active subscription
        # Distinguish: was_paid=True means subscription lapsed, False means trial expired
        was_paid = bool(is_paid)
        return {"status": "expired", "trial_days_left": 0, "expires_at": None, "was_paid": was_paid}
    finally:
        cursor.close()
        release_connection(conn)


def activate_subscription(phone: str, months: int = 1):
    """
    Called by the Razorpay webhook after a confirmed payment.
    Extends subscription_expires_at by `months` — stacking correctly if the
    user renews before their current period ends.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE users
            SET is_paid                 = TRUE,
                subscription_expires_at = GREATEST(
                    COALESCE(subscription_expires_at, NOW()),
                    NOW()
                ) + (INTERVAL '1 month' * %s)
            WHERE id = %s
            """,
            (months, phone)
        )
        conn.commit()
    finally:
        cursor.close()
        release_connection(conn)


def save_payment_link_id(phone: str, link_id: str):
    """Store the last Razorpay payment link id to avoid duplicate links."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE users SET last_payment_link_id = %s WHERE id = %s",
            (link_id, phone)
        )
        conn.commit()
    finally:
        cursor.close()
        release_connection(conn)


def get_last_payment_link_id(phone: str):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT last_payment_link_id FROM users WHERE id = %s",
            (phone,)
        )
        row = cursor.fetchone()
        return row[0] if row else None
    finally:
        cursor.close()
        release_connection(conn)


# ─────────────────────────────────────────────────────────────────────────────
# Summary helpers (unchanged)
# ─────────────────────────────────────────────────────────────────────────────

def mark_summary_sent(phone: str):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE users SET last_summary_sent_at = CURRENT_DATE WHERE id = %s",
            (phone,)
        )
        conn.commit()
    finally:
        cursor.close()
        release_connection(conn)


def get_summary_users():
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, business_name
            FROM users
            WHERE morning_summary_enabled = TRUE
            AND (
                last_summary_sent_at IS NULL
                OR last_summary_sent_at < CURRENT_DATE
            )
            """
        )
        rows = cursor.fetchall()
        return [{"id": r[0], "business_name": r[1]} for r in rows]
    finally:
        cursor.close()
        release_connection(conn)
