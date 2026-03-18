import time
from datetime import datetime

from repositories.reminder_repository import (
    fetch_and_lock_due_reminders,
    mark_reminder_sent,
    mark_reminder_failed
)
from repositories.payment_repository import get_payment_for_reminder
from worker.morning_summary_worker import run_morning_summary
from whatsapp import send_whatsapp_message
from config import REMINDER_POLL_INTERVAL, MORNING_SUMMARY_HOUR


def log(msg: str):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [WORKER] {msg}")


def _build_customer_message(task: str, due_at, business_name: str, business_type: str, balance: float) -> str:
    due_str = ""
    if due_at:
        if isinstance(due_at, str):
            due_at = datetime.fromisoformat(due_at)
        due_str = due_at.strftime('%d %b %Y at %I:%M %p')

    balance_line = f"\n💰 Balance due: Rs.{balance:.0f}" if balance > 0 else ""

    templates = {
        "baker":       f"Hi! 🎂 Your order from *{business_name}* is ready on *{due_str}*.{balance_line}\nPlease carry the exact amount. Thank you!",
        "salon":       f"Hi! ✂️ Reminder from *{business_name}* — your appointment is on *{due_str}*.{balance_line}\nSee you soon!",
        "tailor":      f"Hi! 🧵 Your clothes from *{business_name}* will be ready on *{due_str}*.{balance_line}\nPlease collect at your convenience.",
        "tiffin":      f"Hi! 🍱 Your tiffin order from *{business_name}* is confirmed for *{due_str}*.{balance_line}",
        "photography": f"Hi! 📸 Reminder from *{business_name}* — your session is on *{due_str}*.{balance_line}\nLooking forward to it!",
    }

    return templates.get(business_type, f"Hi! Reminder from *{business_name}* — {task}.\nDate: *{due_str}*.{balance_line}")


def maybe_send_morning_summary():
    if datetime.now().hour != MORNING_SUMMARY_HOUR:
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
            message = f"⏰ *Reminder*\n\n{r['task']}"

            # Show due time if available
            if r.get("due_at"):
                due = r["due_at"]
                if isinstance(due, str):
                    due = datetime.fromisoformat(due)
                message += f"\n📅 Due: {due.strftime('%d %b %Y %I:%M %p')}"

            # Show balance if outstanding
            payment = get_payment_for_reminder(r["id"])
            if payment and float(payment["balance"]) > 0:
                message += f"\n💰 Balance pending: Rs.{float(payment['balance']):.0f}"
                message += f"\n\nReply *paid {payment['customer'] or r['task'][:15]}* when collected."

            send_whatsapp_message(r["phone"], message, show_help=False)

            # Notify customer if their number was provided
            if payment and payment.get("customer_phone"):
                customer_msg = _build_customer_message(
                    r["task"],
                    r.get("due_at"),
                    r.get("business_name", "your vendor"),
                    r.get("business_type", "generic"),
                    float(payment["balance"]) if payment.get("balance") else 0
                )
                try:
                    send_whatsapp_message(payment["customer_phone"], customer_msg, show_help=False)
                    log(f"Customer notified → {payment['customer_phone'][:6]}***")
                except Exception as ce:
                    log(f"Customer notify failed: {ce}")

            mark_reminder_sent(r["id"])
            log(f"Sent → {r['phone'][:6]}*** → {r['task'][:40]}")
        except Exception as e:
            log(f"Failed {r['id']}: {e}")
            mark_reminder_failed(r["id"])


def run_worker():
    log("Worker started — reminders every 30s, morning summary at 8 AM")
    while True:
        try:
            process_reminders()
            maybe_send_morning_summary()
        except Exception as e:
            log(f"Worker loop error: {e}")
        time.sleep(REMINDER_POLL_INTERVAL)
