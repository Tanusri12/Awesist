from datetime import datetime, date
from repositories.reminder_repository import get_user_reminders, delete_reminder, find_reminders_by_name, mark_reminder_delivered
from whatsapp import send_whatsapp_message


def _fmt_time(dt) -> str:
    if not dt:
        return ""
    if dt.minute == 0:
        return dt.strftime("%-I %p")
    return dt.strftime("%-I:%M %p")


def _to_dt(val) -> datetime:
    if val is None:
        return None
    if isinstance(val, str):
        return datetime.fromisoformat(val)
    return val


def handle_list_reminders(user_id: str, phone: str):
    reminders = get_user_reminders(user_id)
    if not reminders:
        send_whatsapp_message(
            phone,
            "📭 No upcoming orders.\n\nSave one: Anjali cake 14 Apr 6pm",
            show_help=False
        )
        return

    today = date.today()

    from collections import defaultdict
    by_date = defaultdict(list)
    for i, r in enumerate(reminders, start=1):
        due_dt  = _to_dt(r.get("due_at"))
        rem_dt  = _to_dt(r.get("reminder_time"))
        key_dt  = due_dt or rem_dt
        key_day = key_dt.date() if key_dt else date.max
        by_date[key_day].append((i, r, due_dt, rem_dt))

    lines = ["📅 *Upcoming Orders*\n"]

    from datetime import timedelta as _td
    for day in sorted(by_date.keys()):
        entries = by_date[day]

        if day == today:
            day_label = f"*Today, {day.strftime('%-d %b')}*"
        elif day == today + _td(days=1):
            day_label = f"*Tomorrow, {day.strftime('%-d %b')}*"
        else:
            day_label = f"*{day.strftime('%a %-d %b')}*"

        lines.append(day_label)

        for idx, r, due_dt, rem_dt in entries:
            task       = r.get("task") or "—"
            time_str   = _fmt_time(due_dt) if due_dt else ""
            remind_str = _fmt_time(rem_dt) if rem_dt else ""

            total   = r.get("total")
            advance = r.get("advance")
            balance = r.get("balance")

            if total and float(total) > 0:
                bal = float(balance or 0)
                adv = float(advance or 0)
                if bal <= 0:
                    pay_str = "✅ Paid"
                elif adv > 0:
                    pay_str = f"💰 Rs.{int(bal)} due"
                else:
                    pay_str = f"💰 Rs.{int(float(total))} due"
            else:
                pay_str = ""

            # Build single line: idx. Task · 3 PM 🔔 1 PM · 💰 Rs.X due
            row = f"{idx}. {task}"
            if time_str:
                row += f" · {time_str}"
            if remind_str:
                row += f" 🔔 {remind_str}"
            if pay_str:
                row += f" · {pay_str}"
            lines.append(row)

        lines.append("")

    lines.append("Reply *done 1* when delivered · *unpaid* to collect payments")
    send_whatsapp_message(phone, "\n".join(lines), show_help=False)


def handle_delete_reminder(user_id: str, phone: str, text: str):
    import re
    from conversation_memory import set_state
    parts = text.strip().lower().split()

    # "delete all"
    if len(parts) >= 2 and parts[1] == "all":
        reminders = get_user_reminders(user_id)
        if not reminders:
            send_whatsapp_message(phone, "📭 Nothing to delete.", show_help=False)
            return
        for r in reminders:
            try:
                delete_reminder(r["id"], user_id)
            except Exception:
                pass
        send_whatsapp_message(
            phone,
            f"🗑️ All {len(reminders)} reminder{'s' if len(reminders)>1 else ''} deleted.",
            show_help=False
        )
        return

    numbers = [int(n) for n in re.findall(r'\d+', text)]
    if not numbers:
        send_whatsapp_message(phone, "⚠️ Send: *delete 2*  or  *delete 1 3 5*  or  *delete all*", show_help=False)
        return

    reminders = get_user_reminders(user_id)

    # Single delete — ask for confirmation
    if len(numbers) == 1:
        idx = numbers[0] - 1
        if idx < 0 or idx >= len(reminders):
            send_whatsapp_message(phone, "⚠️ Reminder not found. Send *reminders* to see your list.", show_help=False)
            return
        r = reminders[idx]
        due_dt = _to_dt(r.get("due_at"))
        due_str = due_dt.strftime("%-d %b %-I:%M %p") if due_dt else ""
        balance = float(r.get("balance") or 0)
        pay_str = f"\n   💰 Rs.{int(balance)} balance due" if balance > 0 else ""
        desc = f"📝 {r.get('task', '—')}" + (f"  —  {due_str}" if due_str else "") + pay_str
        set_state(phone, {
            "step": "awaiting_delete_confirm",
            "reminder_id": r["id"],
            "desc": desc,
        })
        send_whatsapp_message(
            phone,
            f"🗑️ Delete this order?\n\n{desc}\n\n"
            f"Reply *yes* to delete  ·  *cancel* to keep it",
            show_help=False
        )
        return

    # Multi-delete — no confirmation needed
    deleted = []
    not_found = []
    for num in sorted(set(numbers), reverse=True):
        index = num - 1
        if index < 0 or index >= len(reminders):
            not_found.append(num)
        else:
            try:
                delete_reminder(reminders[index]["id"], user_id)
                deleted.append(num)
            except Exception:
                not_found.append(num)

    if deleted and not not_found:
        send_whatsapp_message(phone, f"🗑️ Deleted {len(deleted)} orders ({', '.join(str(n) for n in sorted(deleted))}).", show_help=False)
    elif deleted and not_found:
        send_whatsapp_message(
            phone,
            f"🗑️ Deleted: {', '.join(str(n) for n in sorted(deleted))}\n"
            f"⚠️ Not found: {', '.join(str(n) for n in sorted(not_found))}",
            show_help=False
        )
    else:
        send_whatsapp_message(phone, "⚠️ Reminder not found. Send *reminders* to see your list.", show_help=False)


def handle_delete_confirm(user_id: str, phone: str, text: str, state: dict) -> bool:
    """Handle yes/cancel reply to delete confirmation."""
    from conversation_memory import clear_state
    t = text.strip().lower()
    reminder_id = state.get("reminder_id")
    clear_state(phone)

    if t in ("yes", "y", "haan", "ha", "confirm", "delete", "ok"):
        try:
            delete_reminder(reminder_id, user_id)
            send_whatsapp_message(phone, "🗑️ Order deleted.\n\nReply *reminders* · *unpaid*", show_help=False)
        except Exception:
            send_whatsapp_message(phone, "⚠️ Could not delete. Try again.", show_help=False)
    else:
        send_whatsapp_message(phone, "✅ Kept — nothing deleted.\n\nReply *reminders* · *unpaid*", show_help=False)
    return True


def handle_done_reminder(user_id: str, phone: str, text: str):
    """done <number> — mark order as delivered."""
    import re
    from repositories.payment_repository import get_payment_for_reminder
    numbers = [int(n) for n in re.findall(r'\d+', text)]
    if not numbers:
        send_whatsapp_message(phone, "⚠️ Send: *done 2*  (use the number from *reminders* list)", show_help=False)
        return

    reminders = get_user_reminders(user_id)
    idx = numbers[0] - 1
    if idx < 0 or idx >= len(reminders):
        send_whatsapp_message(phone, "⚠️ Order not found. Send *reminders* to see your list.", show_help=False)
        return

    r = reminders[idx]
    reminder_id = r["id"]
    task        = r.get("task", "Order")
    balance     = float(r.get("balance") or 0)

    mark_reminder_delivered(reminder_id, user_id)

    if balance > 0:
        payment = get_payment_for_reminder(reminder_id)
        customer_phone = payment.get("customer_phone") if payment else None
        pay_line = f"\n💰 *Rs.{int(balance)} balance still due*"
        footer = f"\n\npaid {numbers[0]} → mark as collected"
        if customer_phone:
            footer += f"\nremind {numbers[0]} → send payment reminder to customer"
        send_whatsapp_message(
            phone,
            f"✅ *Order #{numbers[0]} marked as delivered!*\n\n"
            f"📝 {task.capitalize()}"
            f"{pay_line}"
            f"{footer}",
            show_help=False
        )
    else:
        send_whatsapp_message(
            phone,
            f"✅ *Order #{numbers[0]} delivered and fully paid! 🎉*\n\n"
            f"📝 {task.capitalize()}\n\n"
            f"Reply *reminders* · *earnings*",
            show_help=False
        )


def handle_find_orders(user_id: str, phone: str, text: str):
    """find <name> — search orders by customer name."""
    # Extract search term after "find"
    import re
    name = re.sub(r'^find\s+', '', text.strip(), flags=re.IGNORECASE).strip()
    if not name:
        send_whatsapp_message(phone, "⚠️ Send: *find Anjali*  (customer name)", show_help=False)
        return

    results = find_reminders_by_name(user_id, name)
    if not results:
        send_whatsapp_message(
            phone,
            f"🔍 No orders found for '{name}'.\n\nSend *reminders* to see all orders.",
            show_help=False
        )
        return

    today = date.today()
    total_from = 0.0
    total_pending = 0.0
    lines = [f"🔍 *Orders for {name.capitalize()}:*\n"]

    for i, r in enumerate(results, 1):
        task    = (r.get("task") or "—").title()
        due_dt  = _to_dt(r.get("due_at"))
        balance = float(r.get("balance") or 0)
        total   = float(r.get("total") or 0)
        status  = r.get("status", "pending")

        due_str = due_dt.strftime("%-d %b, %-I %p") if due_dt else ""
        if due_dt and due_dt.date() < today and status == "pending":
            due_str += " ⚠️ Overdue"

        total_from += total
        total_pending += balance

        if balance <= 0 or status == "completed":
            pay_str = "✅ Paid"
        else:
            pay_str = f"💰 Rs.{int(balance)} due"

        line = f"{i}. {task}"
        if due_str:
            line += f" — {due_str}"
        if pay_str:
            line += f" {pay_str}"
        lines.append(line)

    lines.append("")
    summary = f"Total from {name.capitalize()}: *Rs.{int(total_from):,}*"
    if total_pending > 0:
        summary += f"  ·  Rs.{int(total_pending):,} still pending"
    lines.append(summary)
    lines.append("paid 1 to mark collected · done 1 when delivered")

    send_whatsapp_message(phone, "\n".join(lines), show_help=False)
