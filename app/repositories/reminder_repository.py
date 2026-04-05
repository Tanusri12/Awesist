from psycopg2.extras import RealDictCursor
from repositories.db_pool import get_connection, release_connection
from datetime import datetime


def create_reminder(user_id: str, task: str, reminder_time: datetime):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO users (id) VALUES (%s) ON CONFLICT DO NOTHING",
            (user_id,)
        )
        cursor.execute(
            """
            INSERT INTO reminders (user_id, task, reminder_time)
            VALUES (%s, %s, %s)
            ON CONFLICT (user_id, task, reminder_time) DO NOTHING
            RETURNING id
            """,
            (user_id, task, reminder_time)
        )
        result = cursor.fetchone()
        conn.commit()
        return result[0] if result else False
    except Exception as e:
        conn.rollback()
        print("ERROR creating reminder:", e)
        return False
    finally:
        cursor.close()
        release_connection(conn)


def get_reminder_by_id(reminder_id: int, user_id: str) -> dict:
    """Fetch a single reminder with its payment details for pre-filling the edit template."""
    conn = get_connection()
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute(
            """
            SELECT r.id, r.task, r.due_at, r.reminder_time,
                   p.id AS payment_id, p.total, p.advance, p.customer_phone
            FROM reminders r
            LEFT JOIN payments p ON p.reminder_id = r.id
            WHERE r.id = %s AND r.user_id = %s
            """,
            (reminder_id, user_id)
        )
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        cursor.close()
        release_connection(conn)


def fetch_and_lock_due_reminders(limit: int = 20):
    conn = get_connection()
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute(
            """
            UPDATE reminders SET status = 'processing'
            WHERE id IN (
                SELECT id FROM reminders
                WHERE status = 'pending'
                  AND reminder_time <= (NOW() AT TIME ZONE 'Asia/Kolkata')
                ORDER BY reminder_time
                LIMIT %s FOR UPDATE SKIP LOCKED
            )
            RETURNING id, user_id, task, due_at
            """,
            (limit,)
        )
        reminders = cursor.fetchall()
        conn.commit()

        if not reminders:
            return []

        user_ids = list({r["user_id"] for r in reminders})
        cursor.execute(
            "SELECT id, business_name, business_type FROM users WHERE id = ANY(%s)",
            (user_ids,)
        )
        user_map = {u["id"]: u for u in cursor.fetchall()}

        return [
            {
                "id":            r["id"],
                "phone":         r["user_id"],
                "task":          r["task"],
                "due_at":        r["due_at"],
                "business_name": user_map.get(r["user_id"], {}).get("business_name") or "your vendor",
                "business_type": user_map.get(r["user_id"], {}).get("business_type") or "generic",
            }
            for r in reminders
        ]
    finally:
        cursor.close()
        release_connection(conn)


def mark_reminder_sent(reminder_id: int):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE reminders SET status = 'completed', sent_at = NOW() WHERE id = %s",
            (reminder_id,)
        )
        conn.commit()
    finally:
        cursor.close()
        release_connection(conn)


def mark_reminder_failed(reminder_id: int):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE reminders
            SET status = 'pending',
                retry_count = retry_count + 1,
                last_attempt = NOW()
            WHERE id = %s AND retry_count < 3
            """,
            (reminder_id,)
        )
        conn.commit()
    finally:
        cursor.close()
        release_connection(conn)


def get_user_reminders(user_id: str) -> list:
    conn = get_connection()
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute(
            """
            SELECT r.id, r.task, r.reminder_time, r.due_at,
                   p.total, p.advance,
                   GREATEST(0, COALESCE(p.total, 0) - COALESCE(p.advance, 0)) AS balance
            FROM reminders r
            LEFT JOIN payments p ON p.reminder_id = r.id
            WHERE r.user_id = %s AND r.status = 'pending'
            ORDER BY COALESCE(r.due_at, r.reminder_time)
            """,
            (user_id,)
        )
        return cursor.fetchall()
    finally:
        cursor.close()
        release_connection(conn)


def get_most_recent_reminder(user_id: str) -> dict:
    """Return the most recently created pending reminder for this user, or None."""
    conn = get_connection()
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute(
            """
            SELECT id, task, reminder_time, due_at
            FROM reminders
            WHERE user_id = %s AND status = 'pending'
            ORDER BY id DESC
            LIMIT 1
            """,
            (user_id,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        cursor.close()
        release_connection(conn)


def update_reminder(reminder_id: int, user_id: str, task: str, reminder_time, due_date: str = None, due_time: str = None):
    """Update task, reminder_time and optional due fields on an existing reminder."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE reminders
            SET task = %s, reminder_time = %s, due_at = %s, status = 'pending'
            WHERE id = %s AND user_id = %s
            """,
            (task, reminder_time, _build_due_at(due_date, due_time), reminder_id, user_id)
        )
        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        conn.rollback()
        print("ERROR updating reminder:", e)
        return False
    finally:
        cursor.close()
        release_connection(conn)


def _build_due_at(due_date, due_time):
    if not due_date:
        return None
    try:
        from datetime import datetime
        t = due_time or "09:00"
        return datetime.strptime(f"{due_date} {t}", "%Y-%m-%d %H:%M")
    except Exception:
        return None


def delete_reminder(reminder_id: int, user_id: str):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM reminders WHERE id = %s AND user_id = %s",
            (reminder_id, user_id)
        )
        conn.commit()
    finally:
        cursor.close()
        release_connection(conn)


def get_today_reminders(user_id: str) -> list:
    conn = get_connection()
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute(
            """
            SELECT id, task, reminder_time, due_at
            FROM reminders
            WHERE user_id = %s
            AND status = 'pending'
            AND DATE(reminder_time) = (CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Kolkata')::date
            ORDER BY reminder_time
            """,
            (user_id,)
        )
        return cursor.fetchall()
    finally:
        cursor.close()
        release_connection(conn)


def find_reminders_by_name(user_id: str, name: str) -> list:
    """Search all reminders (pending + completed) where task contains name."""
    conn = get_connection()
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute(
            """
            SELECT r.id, r.task, r.due_at, r.reminder_time, r.status,
                   p.total, p.advance, p.customer_phone,
                   GREATEST(0, COALESCE(p.total, 0) - COALESCE(p.advance, 0)) AS balance
            FROM reminders r
            LEFT JOIN payments p ON p.reminder_id = r.id
            WHERE r.user_id = %s AND LOWER(r.task) LIKE %s
            ORDER BY COALESCE(r.due_at, r.reminder_time) DESC
            LIMIT 10
            """,
            (user_id, f"%{name.lower()}%")
        )
        return cursor.fetchall()
    finally:
        cursor.close()
        release_connection(conn)


def mark_reminder_delivered(reminder_id: int, user_id: str):
    """Mark a reminder as completed (delivered)."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE reminders SET status = 'completed', sent_at = NOW() WHERE id = %s AND user_id = %s",
            (reminder_id, user_id)
        )
        conn.commit()
    finally:
        cursor.close()
        release_connection(conn)


def get_today_reminders_with_payment(user_id: str) -> list:
    """Today's reminders with payment info joined."""
    conn = get_connection()
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute(
            """
            SELECT r.id, r.task, r.reminder_time, r.due_at,
                   p.total, p.advance,
                   GREATEST(0, COALESCE(p.total, 0) - COALESCE(p.advance, 0)) AS balance
            FROM reminders r
            LEFT JOIN payments p ON p.reminder_id = r.id
            WHERE r.user_id = %s
            AND r.status = 'pending'
            AND DATE(COALESCE(r.due_at, r.reminder_time)) = (CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Kolkata')::date
            ORDER BY COALESCE(r.due_at, r.reminder_time)
            """,
            (user_id,)
        )
        return cursor.fetchall()
    finally:
        cursor.close()
        release_connection(conn)