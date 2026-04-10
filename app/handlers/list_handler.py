from datetime import datetime, date
from repositories.reminder_repository import get_user_reminders, delete_reminder, find_reminders_by_name, mark_reminder_delivered, get_reminder_by_booking_ref
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
            "📭 No upcoming bookings.\n\nSave one: Anjali cake 14 Apr 6pm",
            show_help=False
        )
        return

    today = date.today()

    from collections import defaultdict
    by_date = defaultdict(list)
    for r in reminders:
        due_dt  = _to_dt(r.get("due_at"))
        rem_dt  = _to_dt(r.get("reminder_time"))
        key_dt  = due_dt or rem_dt
        key_day = key_dt.date() if key_dt else date.max
        by_date[key_day].append((r, due_dt, rem_dt))

    total_count = sum(len(v) for v in by_date.values())
    lines = [f"📅 *Upcoming Bookings ({total_count})*\n"]

    from datetime import timedelta as _td
    serial = 0
    for day in sorted(by_date.keys()):
        entries = by_date[day]

        if day == today:
            day_label = f"*Today, {day.strftime('%-d %b')}*"
        elif day == today + _td(days=1):
            day_label = f"*Tomorrow, {day.strftime('%-d %b')}*"
        else:
            day_label = f"*{day.strftime('%a %-d %b')}*"

        lines.append(day_label)

        for r, due_dt, rem_dt in entries:
            serial    += 1
            ref        = r.get("booking_ref") or "?"
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

            # First line: serial. Task · time · pay
            row = f"{serial}. {task}"
            if time_str:
                row += f" · {time_str}"
            if remind_str:
                row += f" 🔔 {remind_str}"
            if pay_str:
                row += f" · {pay_str}"
            # Second line: booking ref (indented)
            row += f"\n   🔖 Booking Ref: {ref}"
            lines.append(row)

        lines.append("")

    lines.append("Reply *done #BookingRef* to mark delivered · *unpaid* to collect payments · *help*")
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
            f"🗑️ All {len(reminders)} booking{'s' if len(reminders)>1 else ''} deleted.",
            show_help=False
        )
        return

    numbers = [int(n) for n in re.findall(r'\d+', text)]
    if not numbers:
        send_whatsapp_message(phone, "⚠️ Send: *delete 2*  or  *delete 1 3 5*  or  *delete all*", show_help=False)
        return

    # Single delete — ask for confirmation
    if len(numbers) == 1:
        r = get_reminder_by_booking_ref(user_id, numbers[0])
        if not r:
            send_whatsapp_message(phone, f"⚠️ Booking #{numbers[0]} not found. Send *bookings* to see your list.", show_help=False)
            return
        due_dt = _to_dt(r.get("due_at"))
        due_str = due_dt.strftime("%-d %b %-I:%M %p") if due_dt else ""
        balance = float(r.get("balance") or 0)
        pay_str = f"\n   💰 Rs.{int(balance)} balance due" if balance > 0 else ""
        desc = f"#{numbers[0]}  📝 {r.get('task', '—')}" + (f"  —  {due_str}" if due_str else "") + pay_str
        set_state(phone, {
            "step": "awaiting_delete_confirm",
            "reminder_id": r["id"],
            "desc": desc,
        })
        send_whatsapp_message(
            phone,
            f"🗑️ Delete this booking?\n\n{desc}\n\n"
            f"Reply *yes* to delete  ·  *cancel* to keep it",
            show_help=False
        )
        return

    # Multi-delete — look up each by booking_ref, no confirmation needed
    deleted = []
    not_found = []
    for ref in sorted(set(numbers)):
        r = get_reminder_by_booking_ref(user_id, ref)
        if not r:
            not_found.append(ref)
        else:
            try:
                delete_reminder(r["id"], user_id)
                deleted.append(ref)
            except Exception:
                not_found.append(ref)

    if deleted and not not_found:
        send_whatsapp_message(phone, f"🗑️ Deleted bookings: {', '.join('#'+str(n) for n in sorted(deleted))}.", show_help=False)
    elif deleted and not_found:
        send_whatsapp_message(
            phone,
            f"🗑️ Deleted: {', '.join('#'+str(n) for n in sorted(deleted))}\n"
            f"⚠️ Not found: {', '.join('#'+str(n) for n in sorted(not_found))}",
            show_help=False
        )
    else:
        send_whatsapp_message(phone, f"⚠️ Booking(s) not found. Send *bookings* to see your list.", show_help=False)


def handle_delete_confirm(user_id: str, phone: str, text: str, state: dict) -> bool:
    """Handle yes/cancel reply to delete confirmation."""
    from conversation_memory import clear_state
    t = text.strip().lower()
    reminder_id = state.get("reminder_id")
    clear_state(phone)

    if t in ("yes", "y", "haan", "ha", "confirm", "delete", "ok"):
        try:
            delete_reminder(reminder_id, user_id)
            send_whatsapp_message(phone, "🗑️ Booking deleted.\n\nReply *bookings* · *unpaid*", show_help=False)
        except Exception:
            send_whatsapp_message(phone, "⚠️ Could not delete. Try again.", show_help=False)
    else:
        send_whatsapp_message(phone, "✅ Kept — nothing deleted.\n\nReply *bookings* · *unpaid*", show_help=False)
    return True


def handle_booking_detail(user_id: str, phone: str, ref_num: int):
    """Show full details of a booking by its booking ref number."""
    from repositories.payment_repository import get_payment_for_reminder
    r = get_reminder_by_booking_ref(user_id, ref_num)
    if not r:
        send_whatsapp_message(
            phone,
            f"⚠️ Booking {ref_num} not found.\n\nSend *bookings* to see your list.",
            show_help=False
        )
        return

    task       = r.get("task") or "—"
    status     = r.get("status", "pending").title()
    due_at     = _to_dt(r.get("due_at"))
    rem_time   = _to_dt(r.get("reminder_time"))
    due_str    = due_at.strftime("%-d %b %Y, %-I:%M %p") if due_at else "—"
    rem_str    = rem_time.strftime("%-d %b %Y, %-I:%M %p") if rem_time else "—"

    lines = [
        f"📋 *Booking {ref_num}*\n",
        f"📝 {task}",
        f"📅 Due: {due_str}",
        f"⏰ Your reminder: {rem_str}",
        f"🔖 Status: {status}",
    ]

    pay = get_payment_for_reminder(r["id"]) if r.get("id") else None
    if pay and float(pay.get("total") or 0) > 0:
        total   = float(pay["total"])
        advance = float(pay.get("advance") or 0)
        balance = total - advance
        if balance <= 0:
            lines.append("💰 Fully paid ✅")
        else:
            lines.append(f"💰 Total: Rs.{total:.0f}  ·  Paid: Rs.{advance:.0f}  ·  Balance: Rs.{balance:.0f} due")
        if pay.get("customer_phone"):
            lines.append(f"📲 Customer: {str(pay['customer_phone'])[-10:]}")

    status = r.get("status", "pending")
    actions = []
    if status not in ("delivered", "cancelled"):
        actions.append(f"*edit {ref_num}* to update")
        actions.append(f"*done {ref_num}* to mark delivered")
    if pay and float(pay.get("total") or 0) > float(pay.get("advance") or 0):
        actions.append(f"*paid {ref_num}* to record payment")
    if actions:
        lines.append("\nReply " + " · ".join(actions))
    send_whatsapp_message(phone, "\n".join(lines), show_help=False)


def handle_done_reminder(user_id: str, phone: str, text: str):
    """done <number> — mark order as delivered using booking_ref."""
    import re
    from repositories.payment_repository import get_payment_for_reminder
    numbers = [int(n) for n in re.findall(r'\d+', text)]
    if not numbers:
        send_whatsapp_message(phone, "⚠️ Send: *done 5*  (use the # from your *bookings* list)", show_help=False)
        return

    r = get_reminder_by_booking_ref(user_id, numbers[0])
    if not r:
        send_whatsapp_message(phone, f"⚠️ Booking #{numbers[0]} not found. Send *bookings* to see your list.", show_help=False)
        return

    reminder_id = r["id"]
    task        = r.get("task", "Order")
    balance     = float(r.get("balance") or 0)

    mark_reminder_delivered(reminder_id, user_id)

    booking_ref = r.get("booking_ref") or numbers[0]

    if balance > 0:
        payment        = get_payment_for_reminder(reminder_id)
        customer_phone = payment.get("customer_phone") if payment else None
        pay_line = f"\n💰 *Rs.{int(balance)} balance still due*"
        footer = f"\n\npaid {booking_ref} → mark as collected"
        if customer_phone:
            footer += f"\nremind {booking_ref} → send payment reminder to customer"
        send_whatsapp_message(
            phone,
            f"✅ *Booking #{booking_ref} marked as delivered!*\n\n"
            f"📝 {task.capitalize()}"
            f"{pay_line}"
            f"{footer}",
            show_help=False
        )
    else:
        send_whatsapp_message(
            phone,
            f"✅ *Booking #{booking_ref} delivered and fully paid! 🎉*\n\n"
            f"📝 {task.capitalize()}\n\n"
            f"Reply *bookings* · *earnings*",
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
            f"🔍 No orders found for '{name}'.\n\nSend *bookings* to see all orders.",
            show_help=False
        )
        return

    today = date.today()
    total_from = 0.0
    total_pending = 0.0
    lines = [f"🔍 *Orders for {name.capitalize()}:*\n"]

    for r in results:
        ref     = r.get("booking_ref") or "?"
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

        if status == "delivered":
            pay_str = "✅ Delivered"
        elif status == "notified":
            pay_str = "🔔 Notified"
        elif balance <= 0:
            pay_str = "✅ Paid"
        else:
            pay_str = f"💰 Rs.{int(balance)} due"

        line = f"{task}"
        if due_str:
            line += f" — {due_str}"
        line += f" {pay_str}"
        line += f"\n   Booking Ref: *{ref}*"
        lines.append(line)
        lines.append("")

    summary = f"Total from {name.capitalize()}: *Rs.{int(total_from):,}*"
    if total_pending > 0:
        summary += f"  ·  Rs.{int(total_pending):,} still pending"
    lines.append(summary)
    lines.append("*paid N* to mark collected · *done N* when delivered · *help* for more")

    send_whatsapp_message(phone, "\n".join(lines), show_help=False)
