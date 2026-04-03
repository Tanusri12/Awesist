from datetime import datetime, date
from repositories.reminder_repository import get_user_reminders, delete_reminder
from whatsapp import send_whatsapp_message


def _fmt_time(dt) -> str:
    """Format a datetime to compact time like '6:00 PM' or '11:30 AM'."""
    if not dt:
        return ""
    if dt.minute == 0:
        return dt.strftime("%-I %p")       # "6 PM"
    return dt.strftime("%-I:%M %p")        # "6:30 PM"


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
            "📭 No upcoming orders.\n\n"
            "Save one: _Anjali cake 14 Apr 6pm_",
            show_help=False
        )
        return

    today = date.today()

    # Group by due date (fall back to reminder date)
    from collections import defaultdict
    by_date = defaultdict(list)
    for i, r in enumerate(reminders, start=1):
        due_dt  = _to_dt(r.get("due_at"))
        rem_dt  = _to_dt(r.get("reminder_time"))
        key_dt  = due_dt or rem_dt
        key_day = key_dt.date() if key_dt else date.max
        by_date[key_day].append((i, r, due_dt, rem_dt))

    lines = ["📅 *Upcoming Orders*\n"]

    for day in sorted(by_date.keys()):
        entries = by_date[day]

        # Day header
        from datetime import timedelta as _td
        if day == today:
            day_label = f"*Today, {day.strftime('%-d %b')}*"
        elif day == today + _td(days=1):
            day_label = f"*Tomorrow, {day.strftime('%-d %b')}*"
        else:
            day_label = f"*{day.strftime('%a %-d %b')}*"

        lines.append(day_label)

        for idx, r, due_dt, rem_dt in entries:
            task = r.get("task") or "—"

            # Time
            time_str = _fmt_time(due_dt) if due_dt else ""
            remind_str = _fmt_time(rem_dt) if rem_dt else ""

            # Payment
            total   = r.get("total")
            advance = r.get("advance")
            balance = r.get("balance")

            if total and float(total) > 0:
                bal = float(balance or 0)
                adv = float(advance or 0)
                if bal <= 0:
                    pay_str = "💚 Fully paid"
                elif adv > 0:
                    pay_str = f"💰 Rs.{int(adv)} pd · *Rs.{int(bal)} due*"
                else:
                    pay_str = f"💰 *Rs.{int(float(total))} due*"
            else:
                pay_str = ""

            # Build entry
            header = f"  {idx}. {task}"
            if time_str:
                header += f"  ·  {time_str}"
            lines.append(header)
            if remind_str:
                lines.append(f"     🔔 Remind {remind_str}")
            if pay_str:
                lines.append(f"     {pay_str}")

        lines.append("")   # blank line between date groups

    # Summary footer
    total_unpaid = sum(
        float(r.get("balance") or 0)
        for r in reminders
        if r.get("balance") and float(r["balance"]) > 0
    )
    if total_unpaid > 0:
        lines.append(f"💰 *Rs.{int(total_unpaid)} total pending*")
        lines.append("")

    lines.append("_delete 1  ·  unpaid  ·  earnings_")

    send_whatsapp_message(phone, "\n".join(lines), show_help=False)


def handle_delete_reminder(user_id: str, phone: str, text: str):
    import re
    parts = text.strip().lower().split()

    # "delete all" — remove everything
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

    # "delete 1 3 5" or "delete 1,3,5" — extract all numbers
    numbers = [int(n) for n in re.findall(r'\d+', text)]
    if not numbers:
        send_whatsapp_message(
            phone,
            "⚠️ Send: *delete 2*  or  *delete 1 3 5*  or  *delete all*",
            show_help=False
        )
        return

    reminders = get_user_reminders(user_id)
    deleted = []
    not_found = []

    for num in sorted(set(numbers), reverse=True):  # reverse so indexes don't shift mid-delete
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
        if len(deleted) == 1:
            send_whatsapp_message(phone, f"🗑️ Reminder {deleted[0]} deleted.", show_help=False)
        else:
            send_whatsapp_message(
                phone,
                f"🗑️ Deleted {len(deleted)} reminders ({', '.join(str(n) for n in sorted(deleted))}).",
                show_help=False
            )
    elif deleted and not_found:
        send_whatsapp_message(
            phone,
            f"🗑️ Deleted: {', '.join(str(n) for n in sorted(deleted))}\n"
            f"⚠️ Not found: {', '.join(str(n) for n in sorted(not_found))}",
            show_help=False
        )
    else:
        send_whatsapp_message(
            phone,
            "⚠️ Reminder not found. Send *reminders* to see your list.",
            show_help=False
        )