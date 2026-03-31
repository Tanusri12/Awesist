from datetime import datetime
from repositories.reminder_repository import get_user_reminders, delete_reminder
from whatsapp import send_whatsapp_message


def handle_list_reminders(user_id: str, phone: str):
    reminders = get_user_reminders(user_id)
    if not reminders:
        send_whatsapp_message(
            phone,
            "📭 You don't have any reminders yet.\n\n"
            "Try: _Send cake to Anjali on 13th April at 6pm_"
        )
        return
    message = "📋 *Your reminders:*\n\n"
    for i, r in enumerate(reminders, start=1):
        rt = r["reminder_time"]
        if isinstance(rt, str):
            rt = datetime.fromisoformat(rt)
        due = r.get("due_at")
        if due and isinstance(due, str):
            due = datetime.fromisoformat(due)
        message += f"{i}. {r['task']}\n"
        message += f"   ⏰ Remind: {rt.strftime('%d %b %Y %I:%M %p')}\n"
        if due:
            message += f"   📅 Due: {due.strftime('%d %b %Y %I:%M %p')}\n"
        message += "\n"
    message += "Reply: *delete <number>*  ·  *unpaid* to see balances"
    send_whatsapp_message(phone, message)


def handle_delete_reminder(user_id: str, phone: str, text: str):
    try:
        index     = int(text.strip().split()[1]) - 1
        reminders = get_user_reminders(user_id)
        if index < 0 or index >= len(reminders):
            send_whatsapp_message(phone, "⚠️ Reminder not found. Send *reminders* to see your list.")
            return
        delete_reminder(reminders[index]["id"], user_id)
        send_whatsapp_message(phone, "🗑️ Reminder deleted.")
    except (IndexError, ValueError):
        send_whatsapp_message(phone, "⚠️ Send: *delete 2*  (use the number from your list)")