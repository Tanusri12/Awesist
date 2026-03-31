from repositories.reminder_repository import get_user_reminders, delete_reminder
from whatsapp import send_whatsapp_message
from conversation_memory import clear_state
from datetime import datetime


def handle_command(phone: str, text: str, user: dict = None) -> bool:
    msg = text.lower().strip()

    if msg in ["help", "menu", "commands", "?"]:
        send_whatsapp_message(
            phone,
            "🤖 *Awesist — Commands*\n\n"
            "📋 *reminders* → upcoming orders\n"
            "💰 *unpaid* → pending balances\n"
            "✅ *paid <name or number>* → mark collected\n"
            "📊 *earnings* → this month's income\n"
            "💳 *track <name> total <amt>* → payment only\n"
            "❌ *delete <number>* → remove a reminder\n"
            "🚫 *cancel* → cancel current action\n\n"
            "_Reply *how* to see message examples_",
            show_help=False
        )
        return True

    if msg in ["how", "example", "examples", "format", "how to"]:
        send_whatsapp_message(
            phone,
            "💡 *How to add orders*\n\n"
            "_Anjali cake 13th April 5pm_\n"
            "_Anjali cake 13th April 5pm 9876543210_ ← notify customer\n"
            "_Anjali cake 13th April 5pm total 1200 advance 300_ ← track payment\n"
            "_Anjali cake 13th April 5pm remind day before_ ← custom reminder\n\n"
            "*Payment only (no date needed):*\n"
            "_track Anjali total 1200 advance 300_\n\n"
            "📅 Dates: today, tomorrow, next Monday, 13th April…\n"
            "🌐 English only.\n\n"
            "_Reply *help* for all commands_",
            show_help=False
        )
        return True

    if msg == "cancel":
        clear_state(phone)
        send_whatsapp_message(phone, "👍 Cancelled.", show_help=False)
        return True

    if msg in ["reminders", "my reminders", "list", "show reminders", "list reminders"]:
        user_id   = phone if not user else user["id"]
        reminders = get_user_reminders(user_id)
        if not reminders:
            send_whatsapp_message(
                phone,
                "📭 You don't have any reminders yet.\n\n"
                "Try: _Send cake to Anjali on 13th April at 6pm_"
            )
            return True
        message = "📋 *Your reminders*\n\n"
        for i, r in enumerate(reminders, start=1):
            dt = r["reminder_time"]
            if isinstance(dt, str):
                dt = datetime.fromisoformat(dt)
            due = r.get("due_at")
            if due and isinstance(due, str):
                due = datetime.fromisoformat(due)
            message += f"{i}. {r['task']}\n"
            message += f"   ⏰ Remind: {dt.strftime('%d %b %Y %I:%M %p')}\n"
            if due:
                message += f"   📅 Due: {due.strftime('%d %b %Y %I:%M %p')}\n"
            message += "\n"
        message += "Reply: *delete <number>*  ·  *unpaid* to see balances"
        send_whatsapp_message(phone, message)
        return True

    if msg.startswith("delete"):
        parts = msg.split()
        if len(parts) != 2:
            send_whatsapp_message(phone, "❌ Send: *delete 2*")
            return True
        try:
            index = int(parts[1]) - 1
        except ValueError:
            send_whatsapp_message(phone, "❌ Send: *delete 2*")
            return True
        user_id   = phone if not user else user["id"]
        reminders = get_user_reminders(user_id)
        if index < 0 or index >= len(reminders):
            send_whatsapp_message(phone, "❌ Reminder not found. Send *reminders* to see your list.")
            return True
        delete_reminder(reminders[index]["id"], user_id)
        send_whatsapp_message(phone, "✅ Reminder deleted.")
        return True

    return False