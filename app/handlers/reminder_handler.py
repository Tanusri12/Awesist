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
            "_Priya cake 13th April 5pm_\n"
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
        customer_phone, total, advance
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
    customer_phone, total, advance
):
    """
    Called once we know due_date + due_time.
    Saves the reminder with a default 2-hr reminder, then:
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
            "_Priya cake tomorrow at 5pm_\n"
            "_Meena appointment 20th April at 11am_",
            show_help=False
        )
        return

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

    # ── Total known → save payment and confirm fully ─────────────────
    if total is not None:
        customer     = _extract_customer(task)
        adv_amount   = min(float(advance or 0), float(total))
        balance      = float(total) - adv_amount
        create_payment(
            user_id=user_id, reminder_id=reminder_id, customer=customer,
            total=float(total), advance=adv_amount, customer_phone=customer_phone
        )
        set_state(phone, {"step": "just_saved", "reminder_id": reminder_id})
        payment_line = (
            f"💰 Rs.{adv_amount:.0f} advance  ·  Rs.{balance:.0f} balance pending"
            if balance > 0 else "💰 Fully paid ✅"
        )
        notify_line = "\n📱 Customer will be notified on the due date." if customer_phone else ""
        send_whatsapp_message(
            phone,
            f"✅ *All saved!*\n\n"
            f"📝 {task}\n"
            f"📅 Due: {due_display}\n"
            f"⏰ Reminder: {reminder_display}\n"
            f"{payment_line}{notify_line}\n\n"
            f"Reply *unpaid* to see pending balances  ·  *edit* to update this"
        )
        return

    # ── Phone known, no total → one more question ─────────────────────
    if customer_phone:
        set_state(phone, {
            "step": "awaiting_payment",
            "task": task, "due_display": due_display,
            "reminder_id": reminder_id, "reminder_display": reminder_display,
            "customer_phone": customer_phone
        })
        send_whatsapp_message(
            phone,
            f"✅ Reminder set!\n\n"
            f"📝 {task}\n📅 Due: {due_display}\n"
            f"⏰ Reminder: {reminder_display}\n\n"
            f"💰 What's the total order amount?\n\n"
            f"Reply with amount e.g. *850*  ·  or *skip*"
        )
        return

    # ── Nothing extra → save and done ────────────────────────────────
    set_state(phone, {"step": "just_saved", "reminder_id": reminder_id})
    send_whatsapp_message(
        phone,
        f"✅ *Saved!*\n\n"
        f"📝 {task}\n"
        f"📅 Due: {due_display}\n"
        f"⏰ Reminder: {reminder_display} _(2 hrs before)_\n\n"
        f"Reply *unpaid* to track payments  ·  *reminders* to see all  ·  *edit* to update this"
    )


def _handle_just_saved(user_id: str, phone: str, text: str, state: dict) -> bool:
    """
    State right after a reminder is saved.
    Only 'edit' is handled here — everything else falls through to normal routing.
    """
    if text.lower().strip() not in ("edit", "update", "change"):
        # Not an edit request — clear the just_saved state and let normal routing handle it
        clear_state(phone)
        return False

    reminder_id = state.get("reminder_id")
    if not reminder_id:
        clear_state(phone)
        send_whatsapp_message(phone, "⚠️ Nothing to edit. Please save a reminder first.")
        return True

    set_state(phone, {"step": "awaiting_edit", "reminder_id": reminder_id})
    send_whatsapp_message(
        phone,
        "✏️ *Update reminder*\n\n"
        "Send the corrected details — just like you normally would:\n\n"
        "_Priya cake 15th April 6pm_\n"
        "_Meena appointment 20th April at 11am total 2500 advance 500_\n\n"
        "I'll update the saved reminder.",
        show_help=False
    )
    return True


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
            "Please include a date, e.g. _Priya cake 15th April 6pm_"
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

    if step == "just_saved":
        return _handle_just_saved(user_id, phone, text, state)

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
        customer_phone, total, advance
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
        customer_phone, total, advance
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
        notify_line = "\n📱 Customer will be notified on the due date." if customer_phone else ""
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

    state["step"] = "awaiting_payment"
    if customer_phone:
        state["customer_phone"] = customer_phone
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
        "customer_phone":   state.get("customer_phone")
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

    create_payment(
        user_id=user_id,
        reminder_id=reminder_id,
        customer=customer,
        total=total,
        advance=advance,
        customer_phone=customer_phone
    )

    clear_state(phone)

    payment_line = f"💰 Rs.{advance:.0f} advance received" if advance > 0 else "💰 No advance"
    if balance > 0:
        payment_line += f" · Rs.{balance:.0f} balance pending"
    else:
        payment_line = "💰 Fully paid ✅"

    send_whatsapp_message(
        phone,
        f"✅ *All saved!*\n\n"
        f"📝 {task}\n"
        f"📅 Due: {due_display}\n"
        f"⏰ Reminder: {reminder_disp}\n"
        f"{payment_line}\n\n"
        f"Reply *unpaid* anytime to see pending balances."
    )
    return True


# --------------------------------------------------
# Helpers
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