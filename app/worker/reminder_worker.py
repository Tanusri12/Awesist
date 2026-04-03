import time
from datetime import datetime

from repositories.reminder_repository import (
    fetch_and_lock_due_reminders,
    mark_reminder_sent,
    mark_reminder_failed
)
from repositories.payment_repository import (
    get_payment_for_reminder,
    get_pending_customer_notifications,
    mark_customer_notified,
)
from worker.morning_summary_worker import run_morning_summary
from whatsapp import send_whatsapp_message
from config import REMINDER_POLL_INTERVAL, MORNING_SUMMARY_HOUR

TRIAL_CUSTOMER_NOTIFY_LIMIT = 3


def log(msg: str):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [WORKER] {msg}")


def _build_customer_message(task: str, due_at, business_name: str, business_type: str, balance: float) -> str:
    if due_at and isinstance(due_at, str):
        due_at = datetime.fromisoformat(due_at)

    time_str = due_at.strftime("%-I:%M %p") if due_at and due_at.minute != 0 else (due_at.strftime("%-I %p") if due_at else "")

    balance_line = (
        f"\n\n💰 *Balance due: Rs.{balance:.0f}*"
        if balance > 0 else ""
    )

    time_line = f"\n⏰ *Today at {time_str}*" if time_str else ""

    return (
        f"Hi! 👋\n\n"
        f"Heads up! Your order from *{business_name}* is scheduled for *today*.{time_line}"
        f"{balance_line}\n\n"
        f"Have a great day! 😊"
    )


def _ist_now():
    """Current datetime in IST (UTC+5:30). No external lib needed."""
    from datetime import timezone, timedelta
    IST = timezone(timedelta(hours=5, minutes=30))
    return datetime.now(IST)


def maybe_send_morning_summary():
    if _ist_now().hour != MORNING_SUMMARY_HOUR:
        return
    try:
        run_morning_summary()
    except Exception as e:
        log(f"Morning summary error: {e}")


def process_reminders():
    try:
        reminders = fetch_and_lock_due_reminders()
    except Exception as e:
        log(f"DB error: {e}")
        return
    if not reminders:
        return
    log(f"{len(reminders)} reminder(s) due")
    for r in reminders:
        try:
            task_title = r["task"].title() if r["task"] else "Order"
            message = f"⏰ *{task_title}*"

            # Due time
            if r.get("due_at"):
                due = r["due_at"]
                if isinstance(due, str):
                    due = datetime.fromisoformat(due)
                message += f"\n📅 Due: {due.strftime('%d %b, %I:%M %p')}"

            # Payment info
            payment = get_payment_for_reminder(r["id"])
            if payment:
                if payment.get("customer_phone"):
                    message += f"\n📲 {str(payment['customer_phone'])[-10:]}"
                if float(payment.get("balance") or 0) > 0:
                    message += f"\n💰 Rs.{float(payment['balance']):.0f} balance pending"
                    message += f"\n\nReply *unpaid* → mark as collected"

            send_whatsapp_message(r["phone"], message, show_help=False)

            mark_reminder_sent(r["id"])
            log(f"Sent → {r['phone'][:6]}*** → {r['task'][:40]}")
        except Exception as e:
            log(f"Failed {r['id']}: {e}")
            mark_reminder_failed(r["id"])


def process_customer_notifications():
    """
    Independently fire customer notifications based on customer_notify_at.
    Completely decoupled from vendor reminder timing.
    """
    try:
        rows = get_pending_customer_notifications()
    except Exception as e:
        log(f"DB error (customer notifications): {e}")
        return
    if not rows:
        return
    log(f"{len(rows)} customer notification(s) due")
    for row in rows:
        try:
            from repositories.user_repository import get_subscription_status
            from repositories.payment_repository import get_customer_notification_count

            vendor_phone = row["vendor_phone"]
            sub      = get_subscription_status(vendor_phone)
            is_trial = sub.get("status") == "trial"
            can_notify = True

            if is_trial:
                notif_count = get_customer_notification_count(row["user_id"])
                if notif_count >= TRIAL_CUSTOMER_NOTIFY_LIMIT:
                    can_notify = False
                    send_whatsapp_message(
                        vendor_phone,
                        f"📢 *Trial limit reached*\n\n"
                        f"You've used all {TRIAL_CUSTOMER_NOTIFY_LIMIT} free customer notifications.\n"
                        f"*{row.get('customer') or 'Your customer'}* did not receive a reminder.\n\n"
                        f"Subscribe to *Pro (₹299/month)* to keep sending automatic alerts to customers.\n\n"
                        f"Reply *subscribe* to continue. 🚀",
                        show_help=False
                    )
                    log(f"Trial limit — customer notify blocked for {vendor_phone[:6]}***")

            if can_notify:
                customer_msg = _build_customer_message(
                    row["task"],
                    row.get("due_at"),
                    row.get("business_name", "your vendor"),
                    row.get("business_type", "generic"),
                    float(row["balance"]) if row.get("balance") else 0
                )
                send_whatsapp_message(row["customer_phone"], customer_msg, show_help=False)
                log(f"Customer notified → {row['customer_phone'][:6]}***")

            mark_customer_notified(row["payment_id"])
        except Exception as e:
            log(f"Customer notify failed (payment {row.get('payment_id')}): {e}")


def run_worker():
    log("Worker started — reminders every 30s, morning summary at 8 AM")
    while True:
        try:
            process_reminders()
            process_customer_notifications()
            maybe_send_morning_summary()
        except Exception as e:
            log(f"Worker loop error: {e}")
        time.sleep(REMINDER_POLL_INTERVAL)
