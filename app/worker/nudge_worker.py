"""
Onboarding Nudge Worker
=======================
Sends engagement nudges to trial users on specific days to build habit
and drive conversion to paid.

Nudge Schedule:
  Day 3  — "Haven't added orders yet?" or "Great start — here's a tip"
  Day 7  — "One week in — here's your stats"
  Day 14 — "Halfway through trial — here's what you've done"

Days 25/27/29 nudges are handled by _check_subscription() in incoming_msg_processor.py

Runs once daily (called from morning_summary_worker schedule).
"""

import time
import logging
from datetime import datetime, timedelta

from repositories.db_pool import get_connection, release_connection
from repositories.reminder_repository import get_user_reminders
from repositories.payment_repository import get_trial_stats
from whatsapp import send_whatsapp_message

logger = logging.getLogger(__name__)


# ── Ensure nudges_sent column exists ─────────────────────────────────────────

def _ensure_nudges_column():
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS nudges_sent TEXT DEFAULT ''
        """)
        conn.commit()
    except Exception as e:
        logger.warning("Could not ensure nudges_sent column: %s", e)
        conn.rollback()
    finally:
        cursor.close()
        release_connection(conn)


# ── Fetch trial users who need a nudge ───────────────────────────────────────

def _get_trial_users():
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, business_name, business_type, trial_started_at,
                   COALESCE(nudges_sent, '') as nudges_sent
            FROM users
            WHERE trial_started_at IS NOT NULL
              AND business_name IS NOT NULL
              AND (is_paid = FALSE OR is_paid IS NULL)
              AND (
                  subscription_expires_at IS NULL
                  OR subscription_expires_at > NOW()
              )
        """)
        rows = cursor.fetchall()
        return [
            {
                "id":               r[0],
                "business_name":    r[1],
                "business_type":    r[2] or "generic",
                "trial_started_at": r[3],
                "nudges_sent":      r[4],
            }
            for r in rows
        ]
    finally:
        cursor.close()
        release_connection(conn)


def _mark_nudge_sent(user_id: str, day: int):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE users
            SET nudges_sent = CASE
                WHEN COALESCE(nudges_sent, '') = '' THEN %s::TEXT
                ELSE nudges_sent || ',' || %s::TEXT
            END
            WHERE id = %s
        """, (str(day), str(day), user_id))
        conn.commit()
    except Exception as e:
        logger.error("Failed to mark nudge %d sent for %s: %s", day, user_id[:6], e)
        conn.rollback()
    finally:
        cursor.close()
        release_connection(conn)


# ── Nudge messages ────────────────────────────────────────────────────────────

def _nudge_day3(user: dict, reminder_count: int) -> str:
    name = user["business_name"].split()[0]

    if reminder_count == 0:
        return (
            f"Hey *{name}*! 👋\n\n"
            "You're 3 days into your free trial but haven't added any orders yet.\n\n"
            "It takes just one message to get started:\n\n"
            "_Priya cake 13th April 5pm total 1200 advance 300_\n\n"
            "Try it now — I'll remind you automatically and track the payment. 💪\n\n"
            "Type *how* to see more examples."
        )
    else:
        return (
            f"Hey *{name}*! 🌟\n\n"
            f"Great start — you've already saved *{reminder_count} order(s)*!\n\n"
            "💡 *Pro tip:* Add a customer's number to auto-notify them when their order is ready:\n\n"
            "_Priya cake 13th April 5pm 9876543210_\n\n"
            "Priya gets a WhatsApp reminder automatically. No extra effort from you! 📱"
        )


def _nudge_day7(user: dict, stats: dict) -> str:
    name = user["business_name"].split()[0]
    total = stats.get("total_reminders", 0)
    collected = int(stats.get("collected_overall", 0))
    pending = int(stats.get("pending_balance", 0))

    lines = [f"One week with Awesist, *{name}*! 🎉\n"]

    if total:
        lines.append(f"📦 *{total}* orders saved so far")
    if collected:
        lines.append(f"💰 *Rs.{collected}* collected from customers")
    if pending:
        lines.append(f"💸 *Rs.{pending}* still pending — type *unpaid* to see who owes you")

    if not total:
        lines.append("You haven't added any orders yet — your trial is running out!")
        lines.append("\nJust type an order naturally:\n_Priya cake 13th April 5pm_")
    else:
        lines.append("\nKeep adding orders and I'll make sure you never miss a reminder. ⏰")
        lines.append("\nType *earnings* to see your income this month 📊")

    return "\n".join(lines)


def _nudge_day14(user: dict, stats: dict) -> str:
    name = user["business_name"].split()[0]
    total = stats.get("total_reminders", 0)
    collected = int(stats.get("collected_overall", 0))
    pending = int(stats.get("pending_balance", 0))
    upcoming = stats.get("upcoming", 0)

    lines = [f"*{name}*, you're halfway through your free trial! ⏳\n"]
    lines.append("Here's what Awesist has done for you:\n")

    if total:
        lines.append(f"✅ *{total}* orders tracked")
    if collected:
        lines.append(f"💰 *Rs.{collected}* collected")
    if pending:
        lines.append(f"💸 *Rs.{pending}* pending from customers")
    if upcoming:
        lines.append(f"⏰ *{upcoming}* upcoming reminders ready to fire")

    lines.append(
        f"\n15 days left on your trial. After that, keep everything going for just "
        f"*Rs.99/month* — less than Rs.4 a day! 🚀"
    )

    if pending or upcoming:
        lines.append(
            f"\nDon't let Rs.{pending or upcoming} disappear when the trial ends.\n\n"
            "Reply *subscribe* to continue."
        )

    return "\n".join(lines)


# ── Main runner ───────────────────────────────────────────────────────────────

def run_nudge_worker():
    """Run once — checks all trial users and sends due nudges."""
    _ensure_nudges_column()

    users = _get_trial_users()
    sent = 0
    now = datetime.utcnow()

    for user in users:
        user_id = user["id"]
        trial_started = user["trial_started_at"]
        if not trial_started:
            continue

        # Handle timezone-aware vs naive datetime
        if hasattr(trial_started, 'tzinfo') and trial_started.tzinfo is not None:
            from datetime import timezone
            now_aware = datetime.now(timezone.utc)
            days_in = (now_aware - trial_started).days
        else:
            days_in = (now - trial_started).days

        already_sent = set(user["nudges_sent"].split(",")) if user["nudges_sent"] else set()

        try:
            # Fetch stats once for day 7 and 14 nudges
            stats = None

            # ── Day 3 nudge ──────────────────────────────────────────────
            if days_in >= 3 and "3" not in already_sent:
                reminders = get_user_reminders(user_id)
                msg = _nudge_day3(user, len(reminders))
                send_whatsapp_message(user_id, msg, show_help=False)
                _mark_nudge_sent(user_id, 3)
                already_sent.add("3")
                sent += 1
                logger.info("Day 3 nudge sent to %s***", user_id[:6])

            # ── Day 7 nudge ──────────────────────────────────────────────
            elif days_in >= 7 and "7" not in already_sent:
                if stats is None:
                    stats = get_trial_stats(user_id)
                msg = _nudge_day7(user, stats)
                send_whatsapp_message(user_id, msg, show_help=False)
                _mark_nudge_sent(user_id, 7)
                already_sent.add("7")
                sent += 1
                logger.info("Day 7 nudge sent to %s***", user_id[:6])

            # ── Day 14 nudge ─────────────────────────────────────────────
            elif days_in >= 14 and "14" not in already_sent:
                if stats is None:
                    stats = get_trial_stats(user_id)
                msg = _nudge_day14(user, stats)
                send_whatsapp_message(user_id, msg, show_help=False)
                _mark_nudge_sent(user_id, 14)
                sent += 1
                logger.info("Day 14 nudge sent to %s***", user_id[:6])

        except Exception as e:
            logger.error("Nudge error for %s***: %s", user_id[:6], e)

    logger.info("Nudge worker done — sent %d nudges to %d users", sent, len(users))
    return sent
