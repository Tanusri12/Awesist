"""
Reminder creation flow.

Fast path (single message):
  If the vendor's first message already contains date + time, the bot
  calculates a default reminder (2 hrs before), saves everything, and
  confirms in one reply — no back-and-forth.

  Optional fields extracted from the same message:
    customer_phone → skips the "customer phone?" step
    total / advance → skips the payment steps entirely

Slow path (step-by-step):
  Only triggered when mandatory fields are missing.
  Steps: awaiting_task_confirm? → awaiting_time → awaiting_reminder_time
         → awaiting_customer_phone → awaiting_payment → awaiting_advance
"""
from datetime import datetime, timedelta
from ai_extractor import extract_reminder_details, parse_template_reply
from conversation_memory import get_state, set_state, clear_state
from repositories.payment_repository import create_payment
from repositories.db_pool import get_connection, release_connection
from whatsapp import send_whatsapp_message


_META_PHRASES = (
    "set a reminder", "set reminder", "create reminder", "add reminder",
    "remind me", "make a reminder", "new reminder", "save reminder",
    "set an order", "create order", "add order",
)

def _is_meta_command(text: str) -> bool:
    """Return True if the message is generic reminder-creation language, not an actual order."""
    t = text.lower().strip()
    return any(t.startswith(p) or t == p for p in _META_PHRASES)


def handle_create_reminder(user_id: str, phone: str, text: str):
    if _is_meta_command(text):
        send_whatsapp_message(
            phone,
            "💡 Just tell me the order details directly — no need for commands!\n\n"
            "*Examples:*\n"
            "_Anjali cake 13th April 5pm_\n"
            "_Meena blouse stitching 20th April at 11am total 800_\n\n"
            "Type *how* to see more examples.",
            show_help=False
        )
        return

    extracted      = extract_reminder_details(text, phone)
    task           = extracted.get("task") or text
    due_date       = extracted.get("date")
    due_time       = extracted.get("time")
    confidence     = extracted.get("confidence", "high")
    customer_phone = extracted.get("customer_phone")
    total          = extracted.get("total")
    advance        = extracted.get("advance")
    reminder_offset        = extracted.get("reminder_offset")
    customer_notify_option = extracted.get("customer_notify_option")

    # ── No date at all → send fill-in template ──────────────────────────
    if not due_date and not due_time:
        _send_template(phone, task, customer_phone, total, advance)
        return

    # ── Resolve partial date/time ────────────────────────────────────────
    if due_time and not due_date:
        due_date = datetime.now().date().isoformat()
    if due_date and not due_time:
        due_time = "12:00"

    due_dt      = _build_datetime(due_date, due_time)
    due_display = due_dt.strftime('%d %b %Y %I:%M %p') if due_dt else f"{due_date} {due_time}"

    _fast_path_with_date(
        user_id, phone, task, due_date, due_time, due_dt, due_display,
        customer_phone, total, advance,
        reminder_offset=reminder_offset,
        customer_notify_option=customer_notify_option
    )


def _default_reminder_time(due_dt: datetime):
    """
    2 hours before due — but:
    - Never in the past
    - Never after (or equal to) the due time itself
    Falls back to 1 minute before due, or None if even that is in the past.
    """
    if not due_dt:
        return None
    now = datetime.now()
    reminder = due_dt - timedelta(hours=2)
    if reminder > now and reminder < due_dt:
        return reminder
    # Fallback: 1 minute before due
    fallback = due_dt - timedelta(minutes=1)
    if fallback > now:
        return fallback
    # Due time is already past — fire immediately
    return now + timedelta(seconds=30)


def _apply_reminder_offset(due_dt: datetime, offset: str):
    """Calculate reminder time from a named offset."""
    if not due_dt or not offset:
        return None
    if offset == "day_before":
        return (due_dt - timedelta(days=1)).replace(hour=9, minute=0, second=0)
    if offset == "morning":
        return due_dt.replace(hour=8, minute=0, second=0)
    if offset == "2hr":
        return due_dt - timedelta(hours=2)
    if offset == "1hr":
        return due_dt - timedelta(hours=1)
    # Absolute datetime: "abs:YYYY-MM-DD HH:MM"
    if offset.startswith("abs:"):
        try:
            return datetime.strptime(offset[4:], "%Y-%m-%d %H:%M")
        except Exception:
            pass

    # Specific time on the due date like "09:00"
    if ":" in offset:
        try:
            h, m = offset.split(":")
            return due_dt.replace(hour=int(h), minute=int(m), second=0)
        except Exception:
            pass
    return None


def _reminder_label(offset: str) -> str:
    """Return a human-readable label for a reminder offset."""
    if not offset:
        return "_(2 hrs before)_"
    if offset == "day_before":
        return "_(day before)_"
    if offset == "morning":
        return "_(morning of due date)_"
    if offset == "2hr":
        return "_(2 hrs before)_"
    if offset == "1hr":
        return "_(1 hr before)_"
    # Absolute datetime or specific time — no extra label needed
    return ""


def _build_due_datetime(due_date: str, due_time: str) -> datetime:
    """Combine YYYY-MM-DD date and HH:MM time into a datetime."""
    try:
        return datetime.strptime(f"{due_date} {due_time}", "%Y-%m-%d %H:%M")
    except Exception:
        return datetime.strptime(due_date, "%Y-%m-%d").replace(hour=9, minute=0)


def _fast_path_with_date(
    user_id: str, phone: str, task: str,
    due_date: str, due_time: str, due_dt,
    due_display: str,
    customer_phone, total, advance,
    reminder_offset=None,
    customer_notify_option=None
):
    """
    Called once we know due_date + due_time.
    Saves the reminder with a default 2-hr reminder (or custom offset), then:
      - if total is known  → save payment and send complete confirmation (done)
      - if phone but no total → jump to awaiting_payment (1 question left)
      - if nothing extra   → save and confirm (done)
    """
    # ── Reject due times that are too soon (< 30 minutes away) ───────────
    min_due = datetime.now() + timedelta(minutes=30)
    if due_dt < min_due:
        clear_state(phone)
        send_whatsapp_message(
            phone,
            "⚠️ Due date is too soon — please set it at least 30 minutes in the future.\n\n"
            "Try a proper date like:\n"
            "_Anjali cake tomorrow at 5pm_\n"
            "_Meena appointment 20th April at 11am_",
            show_help=False
        )
        return

    # ── Compute reminder time (custom offset or default 2hr) ─────────────
    if reminder_offset:
        reminder_dt = _apply_reminder_offset(due_dt, reminder_offset)
        if not reminder_dt:
            # Unrecognised offset — fall back to default
            reminder_dt = _default_reminder_time(due_dt)
            reminder_offset = None
    else:
        reminder_dt = _default_reminder_time(due_dt)

    if not reminder_dt:
        # Edge case: couldn't compute default — ask manually
        set_state(phone, {
            "step": "awaiting_reminder_time",
            "task": task, "due_date": due_date, "due_time": due_time,
            "due_display": due_display,
            "customer_phone": customer_phone, "total": total, "advance": advance
        })
        send_whatsapp_message(
            phone,
            f"Got it!\n\n📝 {task}\n📅 Due: {due_display}\n\n"
            f"⏰ When should I remind you?\n\n"
            f"Reply: *2 hrs before*  ·  *day before*  ·  or a specific time like *1pm*"
        )
        return

    reminder_id = _save_reminder_with_due(user_id, task, reminder_dt, due_date, due_time)
    if not reminder_id:
        clear_state(phone)
        send_whatsapp_message(phone, "⚠️ This reminder already exists.")
        return

    reminder_display = reminder_dt.strftime('%d %b %Y %I:%M %p')

    due_dt_iso = due_dt.isoformat() if due_dt else None

    reminder_label = _reminder_label(reminder_offset)

    # ── Total known → ask about customer notification (if phone known), then save ─
    if total is not None:
        if customer_phone:
            _ask_notify_customer(phone, {
                "user_id": user_id,
                "task": task, "due_display": due_display,
                "reminder_id": reminder_id, "reminder_display": reminder_display,
                "reminder_label": reminder_label,
                "customer_phone": customer_phone,
                "total": total, "advance": advance,
                "due_dt": due_dt_iso,
            }, preset_option=customer_notify_option)
            return
        # No customer phone — save payment directly
        customer   = _extract_customer(task)
        adv_amount = min(float(advance or 0), float(total))
        balance    = float(total) - adv_amount
        create_payment(
            user_id=user_id, reminder_id=reminder_id, customer=customer,
            total=float(total), advance=adv_amount, customer_phone=None, notify_customer=False
        )
        set_state(phone, {"step": "just_saved", "reminder_id": reminder_id})
        payment_line = (
            f"💰 Rs.{adv_amount:.0f} advance  ·  Rs.{balance:.0f} balance pending"
            if balance > 0 else "💰 Fully paid ✅"
        )
        send_whatsapp_message(
            phone,
            f"✅ *All saved!*\n\n"
            f"📝 {task}\n"
            f"📅 Due: {due_display}\n"
            f"⏰ Reminder: {reminder_display}\n"
            f"{payment_line}\n\n"
            f"Reply *unpaid* to see pending balances  ·  *edit* to update this"
        )
        return

    # ── Phone known, no total → ask notify first ──────────────────────
    if customer_phone:
        _ask_notify_customer(phone, {
            "user_id": user_id,
            "task": task, "due_display": due_display,
            "reminder_id": reminder_id, "reminder_display": reminder_display,
            "reminder_label": reminder_label,
            "customer_phone": customer_phone,
            "total": None, "advance": None,
            "due_dt": due_dt_iso,
        }, preset_option=customer_notify_option)
        return

    # ── Nothing extra → save and done, prompt for payment ────────────
    label = _reminder_label(reminder_offset)
    label_str = f" {label}" if label else ""
    set_state(phone, {
        "step": "just_saved",
        "reminder_id": reminder_id,
        "user_id": user_id,
        "task": task,
        "due_date": due_date,
        "due_time": due_time,
        "reminder_display": reminder_display,
    })
    send_whatsapp_message(
        phone,
        f"✅ *Saved!*\n\n"
        f"📝 {task}\n"
        f"📅 Due: {due_display}\n"
        f"⏰ Reminder: {reminder_display}{label_str}\n\n"
        f"💰 Add payment details?\n"
        f"_total 1200 advance 300_  ·  or *skip*"
    )


def _handle_just_saved(user_id: str, phone: str, text: str, state: dict) -> bool:
    """
    State right after a reminder is saved.
    Handles: payment reply, skip, edit — everything else falls through to normal routing.
    """
    t = text.lower().strip()
    reminder_id = state.get("reminder_id")
    task        = state.get("task", "")

    # ── Edit ──────────────────────────────────────────────────────────
    if t in ("edit", "update", "change"):
        if not reminder_id:
            clear_state(phone)
            send_whatsapp_message(phone, "⚠️ Nothing to edit. Please save a reminder first.")
            return True
        set_state(phone, {"step": "awaiting_edit", "reminder_id": reminder_id})
        send_whatsapp_message(
            phone,
            "✏️ *Update reminder*\n\n"
            "Send the corrected details — just like you normally would:\n\n"
            "_Anjali cake 15th April 6pm_\n"
            "_Meena appointment 20th April at 11am total 2500 advance 500_\n\n"
            "I'll update the saved reminder.",
            show_help=False
        )
        return True

    # ── Skip / No ─────────────────────────────────────────────────────
    if t in ("skip", "no", "nahi", "done"):
        clear_state(phone)
        send_whatsapp_message(
            phone,
            "Got it 👍  Reply *how* to see all examples  ·  *reminders* to see your orders",
            show_help=False
        )
        return True

    # ── Payment reply: "total 1200 advance 300" ───────────────────────
    from ai_extractor import _extract_payment_fields
    payment_fields = _extract_payment_fields(text)
    if payment_fields.get("total") and reminder_id:
        from repositories.payment_repository import create_payment
        total      = float(payment_fields["total"])
        advance    = float(payment_fields.get("advance") or 0)
        advance    = min(advance, total)
        balance    = total - advance
        customer   = _extract_customer(task)
        payment_id = create_payment(
            user_id=user_id, reminder_id=reminder_id, customer=customer,
            total=total, advance=advance, customer_phone=None, notify_customer=False
        )

        if balance <= 0:
            payment_line = "💰 Fully paid ✅"
        elif advance == 0:
            payment_line = f"💰 Full amount due: Rs.{balance:.0f}"
        else:
            payment_line = f"💰 Rs.{advance:.0f} paid · Rs.{balance:.0f} balance due"

        set_state(phone, {
            "step": "awaiting_payment_notify",
            "reminder_id": reminder_id,
            "payment_id": payment_id,
            "task": task,
            "due_date": state.get("due_date"),
            "due_time": state.get("due_time"),
            "reminder_display": state.get("reminder_display", ""),
        })
        send_whatsapp_message(
            phone,
            f"✅ *Payment saved!*\n\n"
            f"📝 {task}\n"
            f"{payment_line}\n\n"
            f"📲 Want to notify your client when the order is ready?\n"
            f"Reply their number e.g. _9876543210_\nor *skip*",
            show_help=False
        )
        return True

    # ── Anything else → clear state, route normally ───────────────────
    clear_state(phone)
    return False


def _handle_awaiting_edit(user_id: str, phone: str, text: str, state: dict) -> bool:
    """Parse the corrected message and update the existing reminder in place."""
    from repositories.reminder_repository import update_reminder

    reminder_id = state.get("reminder_id")
    extracted   = extract_reminder_details(text, phone)
    due_date    = extracted.get("date")
    due_time    = extracted.get("time") or "09:00"
    task        = extracted.get("task") or text.strip()

    if not due_date:
        send_whatsapp_message(
            phone,
            "⚠️ I couldn't find a date in that message.\n\n"
            "Please include a date, e.g. _Anjali cake 15th April 6pm_"
        )
        return True

    due_dt       = _build_due_datetime(due_date, due_time)
    reminder_dt  = _default_reminder_time(due_dt)
    due_display  = due_dt.strftime('%d %b %Y %I:%M %p')
    rem_display  = reminder_dt.strftime('%d %b %Y %I:%M %p')

    ok = update_reminder(reminder_id, user_id, task, reminder_dt, due_date, due_time)
    if not ok:
        clear_state(phone)
        send_whatsapp_message(phone, "⚠️ Could not update — reminder may have already fired.")
        return True

    # Handle payment fields if present
    total   = extracted.get("total")
    advance = extracted.get("advance") or 0
    customer_phone = extracted.get("customer_phone")
    if total is not None:
        from repositories.payment_repository import create_payment
        customer = _extract_customer(task)
        create_payment(
            user_id=user_id, reminder_id=reminder_id, customer=customer,
            total=float(total), advance=float(advance), customer_phone=customer_phone
        )

    set_state(phone, {"step": "just_saved", "reminder_id": reminder_id})
    send_whatsapp_message(
        phone,
        f"✅ *Updated!*\n\n"
        f"📝 {task}\n"
        f"📅 Due: {due_display}\n"
        f"⏰ Reminder: {rem_display}\n\n"
        f"Reply *edit* to change again  ·  *reminders* to see all"
    )
    return True


def handle_reminder_state(user_id: str, phone: str, text: str, state: dict) -> bool:
    step = state.get("step")

    if step == "awaiting_template":
        return _handle_awaiting_template(user_id, phone, text, state)

    if step == "awaiting_task_confirm":
        return _handle_awaiting_task_confirm(user_id, phone, text, state)

    if step == "awaiting_time":
        return _handle_awaiting_time(user_id, phone, text, state)

    if step == "awaiting_reminder_time":
        return _handle_awaiting_reminder_time(user_id, phone, text, state)

    if step == "awaiting_notify_customer":
        return _handle_awaiting_notify_customer(user_id, phone, text, state)

    if step == "just_saved":
        return _handle_just_saved(user_id, phone, text, state)

    if step == "awaiting_payment_notify":
        return _handle_awaiting_payment_notify(user_id, phone, text, state)

    if step == "awaiting_payment_notify_time":
        return _handle_awaiting_payment_notify_time(user_id, phone, text, state)

    if step == "awaiting_edit":
        return _handle_awaiting_edit(user_id, phone, text, state)

    if step == "awaiting_customer_phone":
        return _handle_awaiting_customer_phone(user_id, phone, text, state)

    if step == "awaiting_payment":
        return _handle_awaiting_payment(user_id, phone, text, state)

    if step == "awaiting_advance":
        return _handle_awaiting_advance(user_id, phone, text, state)

    return False


# --------------------------------------------------
# State steps
# --------------------------------------------------

def _send_template(phone: str, task: str, customer_phone=None, total=None, advance=None):
    """Send a fill-in template with known fields pre-filled, unknowns shown as hints."""
    task_line    = f"Task: {task}" if task else "Task: [describe the order or appointment]"
    phone_line   = f"Phone: {customer_phone}" if customer_phone else "Phone: [customer number or skip]"
    total_line   = f"Total: {int(total)}" if total is not None else "Total: [order amount or skip]"
    advance_line = f"Advance: {int(advance)}" if advance is not None else "Advance: [amount paid upfront or skip]"

    set_state(phone, {
        "step": "awaiting_template",
        "task": task,
        "customer_phone": customer_phone,
        "total": total,
        "advance": advance
    })

    send_whatsapp_message(
        phone,
        f"📋 *Fill in the date and send back:*\n\n"
        f"{task_line}\n"
        f"Date: [e.g. 13 Apr 6pm]\n"
        f"{phone_line}\n"
        f"{total_line}\n"
        f"{advance_line}"
    )


def _handle_awaiting_template(user_id: str, phone: str, text: str, state: dict) -> bool:
    """
    Handles the vendor's reply to the fill-in template.
    Two modes:
      1. Structured template fill (contains "Date:") → parse all fields at once
      2. Plain date/time → treat as just the date and fast-path from there
    """
    saved_task     = state.get("task") or text
    customer_phone = state.get("customer_phone")
    total          = state.get("total")
    advance        = state.get("advance")

    # --- Mode 1: template fill -----------------------------------------------
    parsed = parse_template_reply(text)
    if parsed:
        task           = parsed.get("task") or saved_task
        due_date       = parsed.get("date")
        due_time       = parsed.get("time")
        customer_phone = parsed.get("customer_phone") or customer_phone
        total          = parsed.get("total") if parsed.get("total") is not None else total
        advance        = parsed.get("advance") if parsed.get("advance") is not None else advance

        if not due_date:
            # Date still missing after fill — re-send template with error hint
            _send_template(phone, task, customer_phone, total, advance)
            send_whatsapp_message(
                phone,
                "⚠️ Couldn't read the date. Fill in the *Date* field and send again."
            )
            return True

        if due_time and not due_date:
            due_date = datetime.now().date().isoformat()
        if due_date and not due_time:
            due_time = "12:00"

        due_dt      = _build_datetime(due_date, due_time)
        due_display = due_dt.strftime('%d %b %Y %I:%M %p') if due_dt else f"{due_date} {due_time}"
        _fast_path_with_date(
            user_id, phone, task, due_date, due_time, due_dt, due_display,
            customer_phone, total, advance
        )
        return True

    # --- Mode 2: plain date/time reply (backward compat) ---------------------
    extracted = extract_reminder_details(text, phone)
    due_date  = extracted.get("date")
    due_time  = extracted.get("time")
    reminder_offset = extracted.get("reminder_offset")

    if not due_date and not due_time:
        # Still nothing — resend the template
        _send_template(phone, saved_task, customer_phone, total, advance)
        send_whatsapp_message(
            phone,
            "⚠️ Couldn't read the date. Fill in the *Date* field and send again."
        )
        return True

    if due_time and not due_date:
        due_date = datetime.now().date().isoformat()
    if due_date and not due_time:
        due_time = "12:00"

    due_dt      = _build_datetime(due_date, due_time)
    due_display = due_dt.strftime('%d %b %Y %I:%M %p') if due_dt else f"{due_date} {due_time}"
    _fast_path_with_date(
        user_id, phone, saved_task, due_date, due_time, due_dt, due_display,
        customer_phone, total, advance, reminder_offset=reminder_offset
    )
    return True


def _handle_awaiting_task_confirm(user_id: str, phone: str, text: str, state: dict) -> bool:
    response = text.strip().lower()
    confirmed = response in ["yes", "haan", "ha", "correct", "ok", "okay", "right", "yep", "yup", "y"]

    if confirmed:
        task = state.get("task")
    else:
        # Treat their reply as the corrected task
        task = text.strip()

    _send_template(phone, task, state.get("customer_phone"), state.get("total"), state.get("advance"))
    return True


def _handle_awaiting_time(user_id: str, phone: str, text: str, state: dict) -> bool:
    extracted = extract_reminder_details(text, phone)
    due_date  = extracted.get("date")
    due_time  = extracted.get("time")
    task      = state.get("task")
    reminder_offset = extracted.get("reminder_offset")

    if not due_date and not due_time:
        send_whatsapp_message(
            phone,
            "⚠️ Couldn't understand that. Try:\n"
            "_tomorrow at 6pm_  or  _13th April 3pm_"
        )
        return True

    if due_time and not due_date:
        due_date = datetime.now().date().isoformat()
    if due_date and not due_time:
        due_time = "12:00"

    due_dt      = _build_datetime(due_date, due_time)
    due_display = due_dt.strftime('%d %b %Y %I:%M %p') if due_dt else f"{due_date} {due_time}"

    # Carry forward any pre-extracted optional fields from state
    customer_phone = state.get("customer_phone")
    total          = state.get("total")
    advance        = state.get("advance")

    # Now that we have date+time, use the fast path via the main handler
    # by rebuilding a synthetic "extracted" dict and delegating
    _fast_path_with_date(
        user_id, phone, task, due_date, due_time, due_dt, due_display,
        customer_phone, total, advance, reminder_offset=reminder_offset
    )
    return True


def _handle_awaiting_reminder_time(user_id: str, phone: str, text: str, state: dict) -> bool:
    task           = state.get("task")
    due_date       = state.get("due_date")
    due_time       = state.get("due_time")
    due_display    = state.get("due_display", "")
    customer_phone = state.get("customer_phone")
    total          = state.get("total")
    advance        = state.get("advance")
    response       = text.lower().strip()
    reminder_dt    = None

    due_dt = _build_datetime(due_date, due_time) if due_date and due_time else None

    if any(x in response for x in ["2 hr", "2hr", "2 hour", "two hour"]):
        if due_dt:
            reminder_dt = due_dt - timedelta(hours=2)

    elif any(x in response for x in ["1 hr", "1hr", "1 hour", "one hour"]):
        if due_dt:
            reminder_dt = due_dt - timedelta(hours=1)

    elif any(x in response for x in ["day before", "1 day", "one day"]):
        if due_dt:
            reminder_dt = (due_dt - timedelta(days=1)).replace(hour=9, minute=0, second=0)

    elif "morning" in response:
        if due_dt:
            reminder_dt = due_dt.replace(hour=8, minute=0, second=0)

    else:
        rem_extracted = extract_reminder_details(text, phone)
        rem_date      = rem_extracted.get("date") or due_date
        rem_time      = rem_extracted.get("time")
        if rem_time:
            reminder_dt = _build_datetime(rem_date, rem_time)

    if not reminder_dt:
        send_whatsapp_message(
            phone,
            "⚠️ Couldn't understand that. Try:\n\n"
            "*2 hrs before*  ·  *day before*  ·  *morning*  ·  *1pm*  ·  *9am on 12 Apr*"
        )
        return True

    if reminder_dt <= datetime.now():
        send_whatsapp_message(
            phone,
            f"⚠️ That comes out to a time in the past.\n\n"
            f"The due date is *{due_display}* — so *2 hrs before* would already be gone.\n\n"
            f"Send a future reminder time — e.g. *17th March 10am* or *day before*"
        )
        return True

    reminder_id = _save_reminder_with_due(user_id, task, reminder_dt, due_date, due_time)
    if not reminder_id:
        clear_state(phone)
        send_whatsapp_message(phone, "⚠️ This reminder already exists.")
        return True

    reminder_display = reminder_dt.strftime('%d %b %Y %I:%M %p')

    # If we already have total → save payment and finish
    if total is not None:
        customer   = _extract_customer(task)
        adv_amount = min(float(advance or 0), float(total))
        balance    = float(total) - adv_amount
        create_payment(
            user_id=user_id, reminder_id=reminder_id, customer=customer,
            total=float(total), advance=adv_amount, customer_phone=customer_phone
        )
        clear_state(phone)
        payment_line = (
            f"💰 Rs.{adv_amount:.0f} advance  ·  Rs.{balance:.0f} balance pending"
            if balance > 0 else "💰 Fully paid ✅"
        )
        display_num = customer_phone[-10:] if customer_phone and len(customer_phone) >= 10 else customer_phone
        notify_line = f"\n📲 {display_num} will be notified on the due date." if customer_phone else ""
        send_whatsapp_message(
            phone,
            f"✅ *All saved!*\n\n📝 {task}\n📅 Due: {due_display}\n"
            f"⏰ Reminder: {reminder_display}\n{payment_line}{notify_line}\n\n"
            f"Reply *unpaid* to see pending balances."
        )
        return True

    # Otherwise continue to customer phone step (skip if already known)
    if customer_phone:
        set_state(phone, {
            "step": "awaiting_payment", "task": task, "due_display": due_display,
            "reminder_id": reminder_id, "reminder_display": reminder_display,
            "customer_phone": customer_phone
        })
        send_whatsapp_message(
            phone,
            f"✅ Reminder set for {reminder_display}\n\n"
            f"💰 What's the total order amount?\n\n"
            f"Reply with amount e.g. *850*  ·  or *skip*"
        )
    else:
        set_state(phone, {
            "step":             "awaiting_customer_phone",
            "task":             task,
            "due_display":      due_display,
            "reminder_id":      reminder_id,
            "reminder_display": reminder_display
        })
        send_whatsapp_message(
            phone,
            f"✅ Reminder set for {reminder_display}\n\n"
            f"📱 Customer's WhatsApp number?\n\n"
            f"I'll send them a reminder too when the time comes.\n\n"
            f"e.g. *9876543210*  ·  or *skip* to not notify them"
        )
    return True


def _handle_awaiting_customer_phone(user_id: str, phone: str, text: str, state: dict) -> bool:
    response = text.strip().lower()
    customer_phone = None

    if response not in ["skip", "no", "nahi", "na", "nope"]:
        customer_phone = _parse_phone(text)
        if customer_phone is None:
            send_whatsapp_message(
                phone,
                "⚠️ Couldn't read that number.\n\n"
                "Send a 10-digit number like *9876543210*  ·  or *skip*"
            )
            return True

    if customer_phone:
        state["customer_phone"] = customer_phone
        _ask_notify_customer(phone, state)
    else:
        state["step"] = "awaiting_payment"
        set_state(phone, state)
        send_whatsapp_message(
            phone,
            f"💰 What's the total order amount?\n\n"
            f"Reply with amount e.g. *850*  ·  or *skip* to skip"
        )
    return True


def _handle_awaiting_payment(user_id: str, phone: str, text: str, state: dict) -> bool:
    task          = state.get("task")
    due_display   = state.get("due_display", "")
    reminder_id   = state.get("reminder_id")
    reminder_disp = state.get("reminder_display", "")
    response      = text.lower().strip()

    if response in ["skip", "no", "nahi", "na", "nope"]:
        clear_state(phone)
        send_whatsapp_message(
            phone,
            f"✅ *Reminder saved!*\n\n"
            f"📝 {task}\n"
            f"📅 Due: {due_display}\n"
            f"⏰ Reminder: {reminder_disp}\n\n"
            f"No payment tracked. Reply *unpaid* anytime to check balances."
        )
        return True

    total = _parse_amount(text)
    if total is None:
        send_whatsapp_message(
            phone,
            "⚠️ Couldn't understand that amount.\n\n"
            "Send a number like *850*  ·  or *skip* to skip"
        )
        return True

    set_state(phone, {
        "step":             "awaiting_advance",
        "task":             task,
        "due_display":      due_display,
        "reminder_id":      reminder_id,
        "reminder_display": reminder_disp,
        "total":            total,
        "customer_phone":   state.get("customer_phone"),
        "notify_customer":  state.get("notify_customer", True)
    })

    send_whatsapp_message(
        phone,
        f"Total: Rs.{total:.0f}\n\n"
        f"💵 Advance received?\n\n"
        f"Reply with amount e.g. *300*  ·  *no advance*  ·  *full* (fully paid)"
    )
    return True


def _handle_awaiting_advance(user_id: str, phone: str, text: str, state: dict) -> bool:
    task          = state.get("task")
    due_display   = state.get("due_display", "")
    reminder_id   = state.get("reminder_id")
    reminder_disp = state.get("reminder_display", "")
    total         = float(state.get("total", 0))
    customer_phone = state.get("customer_phone")
    response      = text.lower().strip()

    customer = _extract_customer(task)

    if response in ["no advance", "no", "nahi", "na", "none", "0"]:
        advance = 0.0
    elif response in ["full", "full payment", "paid", "fully paid"]:
        advance = total
    else:
        advance = _parse_amount(text)
        if advance is None:
            send_whatsapp_message(
                phone,
                "⚠️ Send a number like *300*  ·  *no advance*  ·  *full*"
            )
            return True

    advance = min(advance, total)
    balance = total - advance

    notify_customer    = state.get("notify_customer", True)
    customer_notify_at = None
    cnat_str           = state.get("customer_notify_at")
    if cnat_str:
        try:
            customer_notify_at = datetime.fromisoformat(cnat_str)
        except Exception:
            pass

    create_payment(
        user_id=user_id,
        reminder_id=reminder_id,
        customer=customer,
        total=total,
        advance=advance,
        customer_phone=customer_phone,
        notify_customer=notify_customer,
        customer_notify_at=customer_notify_at
    )

    clear_state(phone)

    payment_line = f"💰 Rs.{advance:.0f} advance received" if advance > 0 else "💰 No advance"
    if balance > 0:
        payment_line += f" · Rs.{balance:.0f} balance pending"
    else:
        payment_line = "💰 Fully paid ✅"

    notify_line = ""
    if notify_customer and customer_notify_at:
        display_num_adv = (state.get("customer_phone") or "")[-10:]
        notify_line = f"\n📲 {display_num_adv} notified: {customer_notify_at.strftime('%d %b, %I:%M %p')}"

    send_whatsapp_message(
        phone,
        f"✅ *All saved!*\n\n"
        f"📝 {task}\n"
        f"📅 Due: {due_display}\n"
        f"⏰ Your reminder: {reminder_disp}{notify_line}\n"
        f"{payment_line}\n\n"
        f"Reply *unpaid* anytime to see pending balances."
    )
    return True


def _ask_notify_customer(phone: str, state: dict, preset_option=None):
    """Ask vendor when to WhatsApp the customer — free text date/time or 'no'."""
    customer_phone   = state.get("customer_phone", "")
    display_num      = customer_phone[-10:] if len(customer_phone) >= 10 else customer_phone
    reminder_display = state.get("reminder_display", "")
    reminder_label   = state.get("reminder_label", "")
    label_str        = f" {reminder_label}" if reminder_label else " _(2 hrs before due)_"
    task             = state.get("task", "your order")
    due_display      = state.get("due_display", "")
    total            = state.get("total")
    balance          = float(total or 0) - float(state.get("advance") or 0)

    # Build a preview of what the customer will receive
    balance_line = f" Balance due: Rs.{balance:.0f}." if balance > 0 else ""
    preview = f'_"Your {task} will be ready on {due_display}.{balance_line}"_'

    set_state(phone, {**state, "step": "awaiting_notify_customer"})
    send_whatsapp_message(
        phone,
        f"⏰ Your reminder: {reminder_display}{label_str}\n\n"
        f"📲 When should I WhatsApp *{display_num}*?\n\n"
        f"They'll receive:\n{preview}\n\n"
        f"Type a time e.g. _1pm_  ·  _4:30pm_\n"
        f"or *no* to skip",
        show_help=False
    )


def _handle_awaiting_notify_customer(user_id: str, phone: str, text: str, state: dict) -> bool:
    """Handle vendor's reply to customer notification timing — free date/time or 'no'."""
    response = text.lower().strip()

    # If this looks like a new full order (long message with payment/order keywords), restart
    import re as _re
    has_payment_keywords = bool(_re.search(r'\b(total|advance|paid|deposit)\b', response))
    has_remind_keyword   = "remind" in response
    is_long_message      = len(text.split()) > 5
    if (has_payment_keywords or has_remind_keyword) and is_long_message:
        clear_state(phone)
        handle_create_reminder(user_id, phone, text)
        return True

    task           = state.get("task")
    due_display    = state.get("due_display", "")
    reminder_id    = state.get("reminder_id")
    reminder_disp  = state.get("reminder_display", "")
    customer_phone = state.get("customer_phone")
    total          = state.get("total")
    advance        = state.get("advance")
    due_dt_str     = state.get("due_dt")

    # ── Calculate customer_notify_at ──────────────────────────────────────
    notify_customer    = True
    customer_notify_at = None
    notify_label       = ""

    no_words = ("no", "nahi", "na", "nope", "n", "don't notify", "dont notify", "skip")
    if response in no_words:
        notify_customer = False
        # One-time nudge — remind them what they're missing
        display_num_nudge = (customer_phone or "")[-10:]
        send_whatsapp_message(
            phone,
            f"📵 Skipped — *{display_num_nudge}* won't be notified.\n\n"
            f"💡 Next time try a time like _4pm_ — I'll WhatsApp them automatically "
            f"so they know the order is ready and carry the exact amount.",
            show_help=False
        )
    else:
        # Parse free-form date/time e.g. "12 Apr 3pm", "tomorrow 9am"
        try:
            from parser.extractors.datetime_extractor import extract_datetime
            custom_dt_parts = extract_datetime(text)
            if custom_dt_parts.get("date"):
                cdate = custom_dt_parts["date"]
                ctime = custom_dt_parts.get("time") or "09:00"
                customer_notify_at = _build_datetime(cdate, ctime)
                notify_label = customer_notify_at.strftime('%d %b, %I:%M %p')
            else:
                send_whatsapp_message(
                    phone,
                    "⚠️ I couldn't read that time.\n\n"
                    "Type a date & time e.g. _12 Apr 3pm_  ·  or *no* to skip",
                    show_help=False
                )
                return True
        except Exception:
            notify_customer = False

    display_num = (customer_phone or "")[-10:]
    notify_line = (
        f"📲 {display_num} notified: {notify_label}"
        if notify_customer and notify_label
        else "📵 No customer notification"
    )

    # ── Total known → save payment and finish ────────────────────────────
    if total is not None:
        adv_amount = min(float(advance or 0), float(total))
        balance    = float(total) - adv_amount
        create_payment(
            user_id=user_id, reminder_id=reminder_id, customer=_extract_customer(task),
            total=float(total), advance=adv_amount,
            customer_phone=customer_phone if notify_customer else None,
            notify_customer=notify_customer,
            customer_notify_at=customer_notify_at
        )
        set_state(phone, {"step": "just_saved", "reminder_id": reminder_id})
        payment_line = (
            f"💰 Rs.{adv_amount:.0f} advance  ·  Rs.{balance:.0f} balance pending"
            if balance > 0 else "💰 Fully paid ✅"
        )
        send_whatsapp_message(
            phone,
            f"✅ *All saved!*\n\n"
            f"📝 {task}\n"
            f"📅 Due: {due_display}\n"
            f"⏰ Your reminder: {reminder_disp}\n"
            f"{notify_line}\n"
            f"{payment_line}\n\n"
            f"Reply *unpaid* to see pending balances  ·  *edit* to update this"
        )
        return True

    # ── Total not yet known → go to payment step ─────────────────────────
    set_state(phone, {
        "step":               "awaiting_payment",
        "task":               task,
        "due_display":        due_display,
        "reminder_id":        reminder_id,
        "reminder_display":   reminder_disp,
        "customer_phone":     customer_phone if notify_customer else None,
        "notify_customer":    notify_customer,
        "customer_notify_at": customer_notify_at.isoformat() if customer_notify_at else None,
    })
    send_whatsapp_message(
        phone,
        f"💰 What's the total order amount?\n\n"
        f"Reply with amount e.g. *850*  ·  or *skip*"
    )
    return True


# --------------------------------------------------
# Helpers
def _handle_awaiting_payment_notify(user_id: str, phone: str, text: str, state: dict) -> bool:
    """Vendor replied with a phone number (or skip) after adding payment details."""
    t = text.strip()
    if t.lower() in ("skip", "no", "nahi", "na", "done"):
        clear_state(phone)
        send_whatsapp_message(phone, "Done 👍  Reply *unpaid* to see pending balances.", show_help=False)
        return True

    customer_phone = _parse_phone(t)
    if not customer_phone:
        send_whatsapp_message(
            phone,
            "⚠️ Please send a valid 10-digit number e.g. _9876543210_\nor *skip* to continue.",
            show_help=False
        )
        return True

    due_date = state.get("due_date")
    due_time = state.get("due_time", "12:00")
    due_dt   = _build_datetime(due_date, due_time) if due_date else None
    display_num = customer_phone[-10:]

    context = f"\nDue: {due_dt.strftime('%d %b, %I:%M %p')}" if due_dt else ""
    set_state(phone, {**state, "step": "awaiting_payment_notify_time", "customer_phone": customer_phone})
    send_whatsapp_message(
        phone,
        f"📲 When should I WhatsApp *{display_num}*?{context}\n\n"
        f"Type a time e.g. _1pm_, _10:30am_\nor *no* to skip",
        show_help=False
    )
    return True


def _handle_awaiting_payment_notify_time(user_id: str, phone: str, text: str, state: dict) -> bool:
    """Vendor replied with a time to notify the customer."""
    import re as _re
    t = text.strip().lower()

    if t in ("no", "skip", "nahi", "na"):
        clear_state(phone)
        send_whatsapp_message(phone, "Done 👍  Reply *unpaid* to see pending balances.", show_help=False)
        return True

    payment_id     = state.get("payment_id")
    customer_phone = state.get("customer_phone")
    due_date       = state.get("due_date")
    due_time       = state.get("due_time", "12:00")
    task           = state.get("task", "")
    due_dt         = _build_datetime(due_date, due_time) if due_date else None

    # Parse time like "1pm", "10:30am"
    notify_at = None
    m = _re.search(r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)', t)
    if m and due_dt:
        hour   = int(m.group(1))
        minute = int(m.group(2) or 0)
        ampm   = m.group(3)
        if ampm == "pm" and hour != 12:
            hour += 12
        elif ampm == "am" and hour == 12:
            hour = 0
        if 0 <= hour <= 23:
            notify_at = due_dt.replace(hour=hour, minute=minute, second=0, microsecond=0)

    if not notify_at:
        send_whatsapp_message(
            phone,
            "⚠️ Couldn't read that time. Try _1pm_ or _10:30am_\nor *no* to skip.",
            show_help=False
        )
        return True

    from repositories.payment_repository import update_payment_notify, get_payment_for_reminder
    update_payment_notify(payment_id, customer_phone, notify_at)

    # Build full summary
    due_display = ""
    reminder_display = state.get("reminder_display", "")
    if due_dt:
        due_display = due_dt.strftime('%d %b, %I:%M %p')

    payment = get_payment_for_reminder(state.get("reminder_id"))
    if payment:
        total_val   = float(payment.get("total") or 0)
        advance_val = float(payment.get("advance") or 0)
        balance_val = float(payment.get("balance") or 0)
        if balance_val <= 0:
            payment_line = "💰 Fully paid ✅"
        elif advance_val == 0:
            payment_line = f"💰 Full amount due: Rs.{balance_val:.0f}"
        else:
            payment_line = f"💰 Rs.{advance_val:.0f} paid · Rs.{balance_val:.0f} balance due"
    else:
        payment_line = ""

    clear_state(phone)
    send_whatsapp_message(
        phone,
        f"✅ *All saved!*\n\n"
        f"📝 {task}\n"
        f"📅 Due: {due_display}\n"
        f"⏰ Your reminder: {reminder_display}\n"
        f"📲 Client notified: {notify_at.strftime('%d %b, %I:%M %p')}\n"
        f"{payment_line}\n\n"
        f"💡 You can also send it all in one message:\n"
        f"_{task} {due_display} 9876543210 total {int(total_val if payment else 0)} advance {int(advance_val if payment else 0)}_\n\n"
        f"It will save:\n"
        f"📝 Task · 📅 Due date · ⏰ Reminder · 📲 Client number · 💰 Payment\n\n"
        f"Reply *edit* to update · *unpaid* to see balances",
        show_help=False
    )
    return True


# --------------------------------------------------

def _build_datetime(date_str: str, time_str: str):
    try:
        return datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
    except Exception:
        return None


def _parse_amount(text: str):
    import re
    text = text.replace(",", "").replace("₹", "").replace("rs", "").replace("Rs", "").strip()
    match = re.search(r'\d+(\.\d+)?', text)
    if match:
        return float(match.group())
    return None


def _parse_phone(text: str):
    """Extract and normalize an Indian mobile number to WhatsApp format (91XXXXXXXXXX)."""
    import re
    digits = re.sub(r'\D', '', text)
    if len(digits) == 10 and digits[0] in "6789":
        return "91" + digits
    if len(digits) == 12 and digits.startswith("91") and digits[2] in "6789":
        return digits
    return None


def _extract_customer(task: str) -> str:
    import re
    match = re.search(r'\b(?:to|for)\s+([A-Z][a-z]+)', task)
    if match:
        return match.group(1)
    match = re.search(r'\b([A-Z][a-z]+)\b', task)
    if match:
        return match.group(1)
    return task[:20]


def _save_reminder_with_due(user_id: str, task: str, reminder_dt, due_date: str, due_time: str):
    due_at = None
    if due_date and due_time:
        due_at = _build_datetime(due_date, due_time)
    elif due_date:
        due_at = _build_datetime(due_date, "00:00")

    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO users (id) VALUES (%s) ON CONFLICT DO NOTHING",
            (user_id,)
        )
        cursor.execute(
            """
            INSERT INTO reminders (user_id, task, reminder_time, due_at)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (user_id, task, reminder_time) DO NOTHING
            RETURNING id
            """,
            (user_id, task, reminder_dt, due_at)
        )
        result = cursor.fetchone()
        conn.commit()
        return result[0] if result else None
    except Exception as e:
        conn.rollback()
        print("ERROR saving reminder:", e)
        return None
    finally:
        cursor.close()
        release_connection(conn)