from psycopg2.extras import RealDictCursor
from repositories.db_pool import get_connection, release_connection
from datetime import datetime


def create_payment_only(user_id: str, customer: str, total: float, advance: float):
    """
    Create a payment record with NO reminder — for payment-only tracking.
    reminder_id is NULL; the entry still shows up in unpaid / earnings.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO payments (user_id, reminder_id, customer, total, advance, status, notify_customer)
            VALUES (%s, NULL, %s, %s, %s, 'pending', FALSE)
            RETURNING id
            """,
            (user_id, customer, total, advance)
        )
        result = cursor.fetchone()
        conn.commit()
        return result[0] if result else None
    except Exception as e:
        conn.rollback()
        print("ERROR creating payment-only record:", e)
        return None
    finally:
        cursor.close()
        release_connection(conn)


def create_payment(user_id: str, reminder_id: int, customer: str, total: float, advance: float, customer_phone: str = None, notify_customer: bool = True):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO payments (user_id, reminder_id, customer, total, advance, status, customer_phone, notify_customer)
            VALUES (%s, %s, %s, %s, %s, 'pending', %s, %s)
            RETURNING id
            """,
            (user_id, reminder_id, customer, total, advance, customer_phone, notify_customer)
        )
        result = cursor.fetchone()
        conn.commit()
        return result[0] if result else None
    except Exception as e:
        conn.rollback()
        print("ERROR creating payment:", e)
        return None
    finally:
        cursor.close()
        release_connection(conn)


def get_unpaid(user_id: str) -> list:
    """All orders with outstanding balance."""
    conn = get_connection()
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute(
            """
            SELECT
                p.id,
                p.reminder_id,
                p.customer,
                p.total,
                p.advance,
                ROUND(p.total - p.advance, 2) AS balance,
                r.task,
                r.due_at
            FROM payments p
            LEFT JOIN reminders r ON r.id = p.reminder_id
            WHERE p.user_id = %s
            AND p.status = 'pending'
            AND p.total > p.advance
            ORDER BY r.due_at ASC NULLS LAST, p.created_at ASC
            """,
            (user_id,)
        )
        return cursor.fetchall()
    finally:
        cursor.close()
        release_connection(conn)


def mark_paid(payment_id: int, user_id: str) -> dict:
    """Mark a payment as fully collected."""
    conn = get_connection()
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute(
            """
            UPDATE payments
            SET status = 'paid', advance = total, paid_at = NOW()
            WHERE id = %s AND user_id = %s
            RETURNING customer, total
            """,
            (payment_id, user_id)
        )
        result = cursor.fetchone()
        conn.commit()
        return dict(result) if result else None
    finally:
        cursor.close()
        release_connection(conn)


def mark_paid_by_reminder(reminder_id: int, user_id: str) -> dict:
    """Mark payment as paid by reminder id."""
    conn = get_connection()
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute(
            """
            UPDATE payments
            SET status = 'paid', advance = total, paid_at = NOW()
            WHERE reminder_id = %s AND user_id = %s
            RETURNING customer, total
            """,
            (reminder_id, user_id)
        )
        result = cursor.fetchone()
        conn.commit()
        return dict(result) if result else None
    finally:
        cursor.close()
        release_connection(conn)


def get_payment_for_reminder(reminder_id: int) -> dict:
    """Get payment record for a reminder — used in worker message."""
    conn = get_connection()
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute(
            """
            SELECT id, customer, customer_phone, total, advance,
                   ROUND(total - advance, 2) AS balance, status, notify_customer
            FROM payments
            WHERE reminder_id = %s
            """,
            (reminder_id,)
        )
        result = cursor.fetchone()
        return dict(result) if result else None
    finally:
        cursor.close()
        release_connection(conn)


def get_total_pending(user_id: str) -> float:
    """Sum of all outstanding balances — for weekly summary."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT COALESCE(SUM(total - advance), 0)
            FROM payments
            WHERE user_id = %s AND status = 'pending'
            """,
            (user_id,)
        )
        result = cursor.fetchone()
        return float(result[0]) if result else 0.0
    finally:
        cursor.close()
        release_connection(conn)


def get_trial_stats(user_id: str):
    """
    Summary of what the vendor has done across their entire usage.
    Used in the trial-expired upsell message to show real value.

    Returns:
        {
            "total_reminders":  int   — all reminders ever created,
            "this_month":       int   — reminders created this calendar month,
            "collected_overall": float — total rupees collected (all time),
            "collected_month":  float — rupees collected this calendar month,
        }
    """
    conn = get_connection()
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM reminders
                 WHERE user_id = %s)                                      AS total_reminders,

                (SELECT COUNT(*) FROM reminders
                 WHERE user_id = %s
                   AND DATE_TRUNC('month', created_at) = DATE_TRUNC('month', NOW()))
                                                                          AS this_month,

                (SELECT COUNT(*) FROM reminders
                 WHERE user_id = %s AND status = 'pending'
                   AND reminder_time > NOW())                              AS upcoming,

                (SELECT COALESCE(SUM(total), 0) FROM payments
                 WHERE user_id = %s AND status = 'paid')                  AS collected_overall,

                (SELECT COALESCE(SUM(total), 0) FROM payments
                 WHERE user_id = %s AND status = 'paid'
                   AND DATE_TRUNC('month', paid_at) = DATE_TRUNC('month', NOW()))
                                                                          AS collected_month,

                (SELECT COALESCE(SUM(total - advance), 0) FROM payments
                 WHERE user_id = %s AND status = 'pending'
                   AND total > advance)                                    AS pending_balance
            """,
            (user_id, user_id, user_id, user_id, user_id, user_id),
        )
        row = cursor.fetchone()
        return {
            "total_reminders":   int(row["total_reminders"]),
            "this_month":        int(row["this_month"]),
            "upcoming":          int(row["upcoming"]),
            "collected_overall": float(row["collected_overall"]),
            "collected_month":   float(row["collected_month"]),
            "pending_balance":   float(row["pending_balance"]),
        }
    except Exception as e:
        print("ERROR get_trial_stats:", e)
        return {"total_reminders": 0, "this_month": 0, "upcoming": 0,
                "collected_overall": 0.0, "collected_month": 0.0, "pending_balance": 0.0}
    finally:
        cursor.close()
        release_connection(conn)


def get_monthly_earnings(user_id: str, year: int, month: int) -> dict:
    """
    Earnings summary for a given calendar month.
    Only counts payments where status = 'paid' and paid_at falls in that month.

    Returns:
        {
            "total":       float  — total rupees collected,
            "order_count": int    — number of completed orders,
            "customers":   list   — [{"customer": str, "amount": float, "orders": int}, ...]
                                    sorted by amount desc, top customers first
        }
    """
    conn = get_connection()
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute(
            """
            SELECT
                customer,
                ROUND(SUM(total), 2)  AS amount,
                COUNT(*)              AS orders
            FROM payments
            WHERE user_id = %s
              AND status   = 'paid'
              AND paid_at IS NOT NULL
              AND EXTRACT(YEAR  FROM paid_at) = %s
              AND EXTRACT(MONTH FROM paid_at) = %s
            GROUP BY customer
            ORDER BY amount DESC
            """,
            (user_id, year, month),
        )
        rows = cursor.fetchall()
        total       = sum(float(r["amount"]) for r in rows)
        order_count = sum(int(r["orders"])   for r in rows)
        return {
            "total":       total,
            "order_count": order_count,
            "customers":   [dict(r) for r in rows],
        }
    finally:
        cursor.close()
        release_connection(conn)


def get_customer_notification_count(user_id: str) -> int:
    """Count how many customer notifications have already been sent for this user."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM reminders r
            JOIN payments p ON p.reminder_id = r.id
            WHERE r.user_id = %s
              AND r.status = 'sent'
              AND p.customer_phone IS NOT NULL
              AND p.notify_customer = TRUE
            """,
            (user_id,)
        )
        result = cursor.fetchone()
        return int(result[0]) if result else 0
    except Exception as e:
        print("ERROR get_customer_notification_count:", e)
        return 0
    finally:
        cursor.close()
        release_connection(conn)