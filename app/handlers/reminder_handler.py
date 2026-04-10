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
from ai_extractor import extract_reminder_details, parse_template_reply, _looks_like_order, _is_clearly_not_order
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
            "Anjali cake 13th April 5pm\n"
            "Meena blouse stitching 20th April at 11am total 800\n\n"
            "Type *how* to see more examples.",
            show_help=False
        )
        return

    # ── Definite non-order (question / greeting / command) → guide the user ──
    if _is_clearly_not_order(text):
        send_whatsapp_message(
            phone,
            "I didn't quite get that 😊\n\n"
            "To save an order, send something like:\n"
            "Anjali cake 14 Apr 6pm\n"
            "Meena blouse 20 Apr 11am total 800\n\n"
            "Type *how* for more examples · *help* for all commands",
            show_help=False
        )
        return

    # ── Check if this is vendor's very first order ───────────────────────
    from repositories.user_repository import get_reminder_count
    is_first_order = get_reminder_count(phone) == 0

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

    # ── Gibberish guard — task must have at least one real word ──────────
    if not _is_real_task(task):
        send_whatsapp_message(
            phone,
            "I couldn't understand that. Please describe your order clearly, e.g.\n\n"
            "Anjali cake 13 Apr 5pm",
            show_help=False
        )
        return

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

    _show_confirm_preview(
        phone, user_id, task, due_date, due_time, due_dt, due_display,
        customer_phone, total, advance,
        reminder_offset=reminder_offset,
        customer_notify_option=customer_notify_option,
        is_first_order=is_first_order
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
        return "(2 hrs before)"
    if offset == "day_before":
        return "(day before)"
    if offset == "morning":
        return "(morning of due date)"
    if offset == "2hr":
        return "(2 hrs before)"
    if offset == "1hr":
        return "(1 hr before)"
    # Absolute datetime or specific time — no extra label needed
    return ""


def _build_due_datetime(due_date: str, due_time: str) -> datetime:
    """Combine YYYY-MM-DD date and HH:MM time into a datetime."""
    try:
        return datetime.strptime(f"{due_date} {due_time}", "%Y-%m-%d %H:%M")
    except Exception:
        return datetime.strptime(due_date, "%Y-%m-%d").replace(hour=9, minute=0)


def _format_due_for_template(due_date: str, due_time: str) -> str:
    """Format parsed date+time into a human-friendly string for the edit template, e.g. '14 Apr 6pm'."""
    try:
        dt = datetime.strptime(f"{due_date} {due_time}", "%Y-%m-%d %H:%M")
        hour, minute = dt.hour, dt.minute
        if hour == 0:
            t = "12am"
        elif hour < 12:
            t = f"{hour}am" if minute == 0 else f"{hour}:{minute:02d}am"
        elif hour == 12:
            t = "12pm" if minute == 0 else f"12:{minute:02d}pm"
        else:
            h = hour - 12
            t = f"{h}pm" if minute == 0 else f"{h}:{minute:02d}pm"
        return dt.strftime(f"%-d %b") + f" {t}"
    except Exception:
        return f"{due_date} {due_time}"


def _show_confirm_preview(
    phone: str, user_id: str, task: str,
    due_date: str, due_time: str, due_dt,
    due_display: str,
    customer_phone, total, advance,
    reminder_offset=None,
    customer_notify_option=None,
    is_first_order=False
):
    """Show parsed order data and ask vendor to confirm before saving anything."""
    # Pre-calculate reminder time so it shows in preview
    if reminder_offset:
        reminder_dt = _apply_reminder_offset(due_dt, reminder_offset)
        if not reminder_dt:
            reminder_dt = _default_reminder_time(due_dt)
            reminder_offset = None
    else:
        reminder_dt = _default_reminder_time(due_dt)

    reminder_display = reminder_dt.strftime('%-d %b %-I:%M %p') if reminder_dt else "—"
    reminder_label   = _reminder_label(reminder_offset)

    # Detect fallback: if default was requested but reminder is < 10 min before due,
    # 2-hr slot was already past — show a clear warning instead of wrong label.
    fallback_warn = ""
    if not reminder_offset and reminder_dt and due_dt:
        gap_mins = (due_dt - reminder_dt).total_seconds() / 60
        if gap_mins < 10:
            fallback_warn = "\n⚠️ 2 hrs before has already passed — reminding just before delivery."
            reminder_label = ""

    label_str = f" {reminder_label}" if reminder_label else ""

    lines = ["📋 *Got it! Is this right?*\n"]
    lines.append(f"📝 {task}")
    lines.append(f"📅 {due_display}")
    lines.append(f"⏰ Reminder: {reminder_display}{label_str}{fallback_warn}")

    if total is not None:
        adv = float(advance or 0)
        bal = float(total) - adv
        if bal > 0:
            lines.append(f"💰 Rs.{int(total)} total · Rs.{int(adv)} advance · Rs.{int(bal)} due")
        else:
            lines.append(f"💰 Rs.{int(total)} ✅ fully paid")

    if customer_phone:
        display = customer_phone[-10:] if len(customer_phone) >= 10 else customer_phone
        lines.append(f"📱 {display}")

    lines.append("\nReply *yes* to save  ·  *edit* to change")

    due_dt_iso = due_dt.isoformat() if due_dt else None

    set_state(phone, {
        "step":                  "awaiting_confirm",
        "user_id":               user_id,
        "task":                  task,
        "due_date":              due_date,
        "due_time":              due_time,
        "due_display":           due_display,
        "reminder_display":      reminder_display,
        "reminder_label":        reminder_label,
        "reminder_offset":       reminder_offset,
        "customer_phone":        customer_phone,
        "total":                 total,
        "advance":               advance,
        "customer_notify_option": customer_notify_option,
        "due_dt":                due_dt_iso,
        "is_first_order":        is_first_order,
    })

    send_whatsapp_message(phone, "\n".join(lines), show_help=False)


def _fast_path_with_date(
    user_id: str, phone: str, task: str,
    due_date: str, due_time: str, due_dt,
    due_display: str,
    customer_phone, total, advance,
    reminder_offset=None,
    customer_notify_option=None,
    is_first_order=False
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
            "Anjali cake tomorrow at 5pm\n"
            "Meena appointment 20th April at 11am",
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

    save_result = _save_reminder_with_due(user_id, task, reminder_dt, due_date, due_time)
    if not save_result:
        clear_state(phone)
        send_whatsapp_message(
            phone,
            "⚠️ A booking for that task and date already exists — not saved again.\n\n"
            "Send *bookings* to see your list, or save a new order with a different date.",
            show_help=False
        )
        return

    reminder_id, booking_ref = save_result
    reminder_display = reminder_dt.strftime('%d %b %Y %I:%M %p')
    due_dt_iso = due_dt.isoformat() if due_dt else None
    reminder_label = _reminder_label(reminder_offset)
    ref_tag = f"Booking *#{booking_ref}*\n"

    # ── Total known → ask about customer notification (if phone known), then save ─
    if total is not None:
        if customer_phone:
            _ask_notify_customer(phone, {
                "user_id": user_id,
                "task": task, "due_display": due_display,
                "reminder_id": reminder_id, "booking_ref": booking_ref,
                "reminder_display": reminder_display,
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
        if is_first_order:
            send_whatsapp_message(
                phone,
                f"🎉 *First booking saved!* {ref_tag}\n"
                f"📝 {task}\n"
                f"📅 Due: {due_display}\n"
                f"⏰ I'll remind you on *{reminder_display}*\n"
                f"{payment_line}\n\n"
                f"You'll get a WhatsApp message when it's time — no app needed.\n\n"
                f"Reply *unpaid* to see pending balances  ·  *edit* to update this",
                show_help=False
            )
        else:
            send_whatsapp_message(
                phone,
                f"✅ *All saved!* {ref_tag}\n"
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
            "reminder_id": reminder_id, "booking_ref": booking_ref,
            "reminder_display": reminder_display,
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
        "booking_ref": booking_ref,
        "user_id": user_id,
        "task": task,
        "due_date": due_date,
        "due_time": due_time,
        "reminder_display": reminder_display,
    })
    if is_first_order:
        send_whatsapp_message(
            phone,
            f"🎉 *First booking saved!* {ref_tag}\n"
            f"📝 {task}\n"
            f"📅 Due: {due_display}\n"
            f"⏰ I'll remind you on *{reminder_display}*{label_str}\n\n"
            f"You'll get a WhatsApp message when it's time — no app needed.\n\n"
            f"💰 Want to track payment for this order?\n"
            f"Type: total 1500 advance 500 (what they owe + what they paid)\n"
            f"Or reply *skip*",
            show_help=False
        )
    else:
        send_whatsapp_message(
            phone,
            f"✅ *Saved!* {ref_tag}\n"
            f"📝 {task}\n"
            f"📅 Due: {due_display}\n"
            f"⏰ Reminder: {reminder_display}{label_str}\n\n"
            f"💰 Want to track payment for this order?\n"
            f"Type: total 1500 advance 500 (what they owe + what they paid)\n"
            f"Or reply *skip*"
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

        # Fetch current values from DB and show a pre-filled copy-paste template
        from repositories.reminder_repository import get_reminder_by_id
        current = get_reminder_by_id(reminder_id, user_id)
        if not current:
            clear_state(phone)
            send_whatsapp_message(phone, "⚠️ Could not find the reminder to edit.")
            return True

        # Format current due date/time and reminder time
        from datetime import datetime as _dt
        due_at = current.get("due_at")
        if due_at:
            if isinstance(due_at, str):
                due_at = _dt.fromisoformat(due_at)
            date_val = due_at.strftime("%-d %b %-I:%M %p")
        else:
            date_val = ""

        rem_at = current.get("reminder_time")
        if rem_at:
            if isinstance(rem_at, str):
                rem_at = _dt.fromisoformat(rem_at)
            remind_val = rem_at.strftime("%-d %b %-I:%M %p")
        else:
            remind_val = ""

        # Strip any junk emoji suffixes that may have been saved in the task
        import re as _re2
        task_val  = (current.get("task") or "").strip()
        task_val  = _re2.sub(r'[\s]*[📅💰📞✏️📝🔔].*$', '', task_val).strip()
        phone_val = (current.get("customer_phone") or "")[-10:] if current.get("customer_phone") else ""
        total     = current.get("total")
        advance   = current.get("advance")
        if total and float(total) > 0:
            bal = float(total) - float(advance or 0)
            pay_val = f"Rs.{int(float(total))} total · Rs.{int(float(advance or 0))} paid · Rs.{int(bal)} due"
        else:
            pay_val = "Not set"

        set_state(phone, {"step": "awaiting_edit", "reminder_id": reminder_id})
        lines = [
            "✏️ *Copy, edit one line, and send back:*\n",
            f"Task: {task_val}",
            f"Date: {date_val}",
        ]
        if remind_val:
            lines.append(f"Reminder: {remind_val}")
        if phone_val:
            lines.append(f"Phone: {phone_val}")
        lines.append(f"Payment: {pay_val}")
        lines.append(
            f"\nTo update payment:\n"
            f"*payment* 1200 advance 300\n"
            f"*payment done* — mark as fully paid"
        )
        send_whatsapp_message(phone, "\n".join(lines), show_help=False)
        return True

    # ── Skip payment → still ask about client notification ────────────
    if t in ("skip", "no", "nahi", "done"):
        set_state(phone, {
            **state,
            "step": "awaiting_payment_notify",
            "payment_id": None,
        })
        send_whatsapp_message(
            phone,
            "📲 Want to WhatsApp your customer when the order is ready?\n"
            "Reply with their number (e.g. 9876543210)\n"
            "They'll get a message automatically when it's done.\n"
            "Or reply *skip*",
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
            f"📲 Want to WhatsApp your customer when the order is ready?\n"
            f"Reply with their number (e.g. 9876543210)\n"
            f"They'll get a message automatically when it's done.\n"
            f"Or reply *skip*",
            show_help=False
        )
        return True

    # ── Anything else → clear state, route normally ───────────────────
    clear_state(phone)
    return False


def _handle_awaiting_confirm(user_id: str, phone: str, text: str, state: dict) -> bool:
    """
    User has been shown a preview of parsed data.
    'yes' → save.   'edit' → show pre-filled template.   anything else → treat as new message.
    """
    t = text.lower().strip()

    YES_WORDS  = {"yes", "y", "ok", "okay", "haan", "ha", "correct", "right", "save", "yep", "yup"}
    EDIT_WORDS = {"edit", "update", "change", "no", "nahi", "nope", "wrong"}

    if t in YES_WORDS:
        due_date = state.get("due_date")
        due_time = state.get("due_time")
        due_dt   = _build_due_datetime(due_date, due_time) if due_date and due_time else None
        due_display = state.get("due_display", "")
        clear_state(phone)
        _fast_path_with_date(
            user_id, phone,
            state.get("task"), due_date, due_time, due_dt, due_display,
            state.get("customer_phone"), state.get("total"), state.get("advance"),
            reminder_offset=state.get("reminder_offset"),
            customer_notify_option=state.get("customer_notify_option"),
            is_first_order=state.get("is_first_order", False),
        )
        return True

    if t in EDIT_WORDS:
        due_date = state.get("due_date", "")
        due_time = state.get("due_time", "")
        date_val = _format_due_for_template(due_date, due_time) if due_date else ""
        _send_template(
            phone,
            state.get("task", ""),
            customer_phone=state.get("customer_phone"),
            total=state.get("total"),
            advance=state.get("advance"),
            date_val=date_val,
        )
        return True

    # Anything else — treat as a brand-new message, clear state
    clear_state(phone)
    return False


def _handle_awaiting_edit(user_id: str, phone: str, text: str, state: dict) -> bool:
    """Handle partial or full updates to an existing reminder."""
    import re as _re
    from repositories.reminder_repository import update_reminder, get_reminder_by_id

    reminder_id = state.get("reminder_id")
    t = text.strip().lower()

    # ── Template-style reply (user copied the edit prompt and filled fields) ─
    # Supports two formats:
    #   Text labels:  "Task: priya cake\n📅 Due: 5 Apr\n📞 Customer: 9591914432"
    #   Emoji labels: "priya cake\n📅 20 apr 6pm\n💰 Rs.850...\n📞 9591914432"
    _is_text_template  = _re.search(r'\btask\s*:', text, _re.I) and _re.search(r'(customer|phone|due|payment)\s*:', text, _re.I)
    _is_emoji_template = _re.search(r'📅', text) and (_re.search(r'📞', text) or _re.search(r'💰', text))
    if _is_text_template or _is_emoji_template:
        def _tfield(label: str):
            m = _re.search(rf'{label}\s*:\s*(.+)', text, _re.I | _re.MULTILINE)
            if not m:
                return None
            v = _re.sub(r'^[\s📅💰📞✏️]+', '', m.group(1)).strip()
            return None if v.lower() in ('not set', 'skip', '-', '', 'na', 'none') else v

        def _emoji_field(emoji: str):
            """Extract value from an emoji-labelled line e.g. '📅 20 apr 6pm'."""
            m = _re.search(rf'{_re.escape(emoji)}\s*(.+)', text, _re.MULTILINE)
            if not m:
                return None
            v = m.group(1).strip()
            # Strip payment detail suffixes like "Rs.850 total · Rs.850 paid · Rs.0 due"
            v = _re.sub(r'Rs\.\d+.*', '', v, flags=_re.I).strip()
            v = _re.sub(r'·.*', '', v).strip()
            return v if v else None

        current = get_reminder_by_id(reminder_id, user_id)
        if not current:
            clear_state(phone)
            return True

        task       = current.get("task", "")
        due_at_cur = current.get("due_at") or current.get("reminder_time")
        if due_at_cur and isinstance(due_at_cur, str):
            due_at_cur = datetime.fromisoformat(due_at_cur)

        changed_lines = []

        # Task — first line of message if no "Task:" label (emoji format)
        new_task = _tfield('task')
        if not new_task and _is_emoji_template:
            # First non-empty line that doesn't start with an emoji is the task
            for line in text.splitlines():
                line = line.strip()
                if line and not _re.match(r'^[📅💰📞✏️]', line):
                    new_task = line
                    break
        if new_task and new_task.lower() != task.lower():
            task = new_task
            changed_lines.append(f"📝 {task}")

        # Due date/time — text label or 📅 emoji line
        due_raw = _tfield('due') or _tfield('date') or _emoji_field('📅')
        new_due_date, new_due_time = None, None
        if due_raw:
            extracted_dt = extract_reminder_details(due_raw, phone)
            new_due_date = extracted_dt.get("date")
            new_due_time = extracted_dt.get("time") or "09:00"
            if new_due_date:
                due_at_cur = _build_due_datetime(new_due_date, new_due_time)
                changed_lines.append(f"📅 {due_at_cur.strftime('%-d %b %-I:%M %p')}")

        # Reminder time — explicit Reminder: field takes priority, else recompute if due changed
        rem_dt = None
        remind_raw = _tfield('reminder')
        if remind_raw:
            extracted_rem = extract_reminder_details(remind_raw, phone)
            rem_date = extracted_rem.get("date")
            rem_time = extracted_rem.get("time")
            if rem_date and rem_time:
                rem_dt = _build_due_datetime(rem_date, rem_time)
                changed_lines.append(f"🔔 Reminder: {rem_dt.strftime('%-d %b %-I:%M %p')}")
        if rem_dt is None and new_due_date:
            rem_dt = _default_reminder_time(due_at_cur)

        # Save reminder update
        update_reminder(reminder_id, user_id, task, rem_dt,
                        new_due_date or None, new_due_time or None)

        # Payment: field — parse total and advance from template reply
        pay_raw = _tfield('payment')
        if pay_raw and pay_raw.lower() not in ('not set', 'skip', ''):
            from ai_extractor import _extract_payment_fields
            from repositories.payment_repository import get_payment_for_reminder, create_payment
            pay_fields = _extract_payment_fields(pay_raw)
            new_total   = pay_fields.get("total")
            new_advance = pay_fields.get("advance")
            if new_total is not None:
                new_advance = min(float(new_advance or 0), float(new_total))
                balance     = float(new_total) - new_advance
                existing_pay = get_payment_for_reminder(reminder_id)
                if existing_pay:
                    from repositories.payment_repository import update_payment
                    update_payment(existing_pay["id"], float(new_total), new_advance)
                else:
                    create_payment(user_id=user_id, reminder_id=reminder_id,
                                   customer=_extract_customer(task),
                                   total=float(new_total), advance=new_advance,
                                   customer_phone=None, notify_customer=False)
                pay_line = (f"💰 Rs.{int(new_total)} total · Rs.{int(new_advance)} paid · Rs.{int(balance)} due"
                            if balance > 0 else f"💰 Rs.{int(new_total)} — Fully paid ✅")
                changed_lines.append(pay_line)

        # Customer phone — text label or 📞 emoji line
        phone_raw = _tfield('customer') or _tfield('phone') or _emoji_field('📞')
        if phone_raw:
            digits = _re.sub(r'\D', '', phone_raw)
            if len(digits) >= 10:
                customer_phone_e164 = '91' + digits[-10:]
                display_num = digits[-10:]
                notify_at, notify_label = _calc_notify_at(due_at_cur)
                from repositories.payment_repository import get_payment_for_reminder, update_payment_notify, create_payment
                existing_pay = get_payment_for_reminder(reminder_id)
                if existing_pay:
                    update_payment_notify(existing_pay["id"], customer_phone_e164, notify_at)
                else:
                    create_payment(user_id=user_id, reminder_id=reminder_id,
                                   customer=_extract_customer(task),
                                   total=0, advance=0, customer_phone=customer_phone_e164,
                                   notify_customer=True, customer_notify_at=notify_at)
                changed_lines.append(f"📞 {display_num} — notified {notify_label}")

        # Always show due + reminder time in confirmation
        if due_at_cur:
            due_line = f"📅 {due_at_cur.strftime('%-d %b %-I:%M %p')}"
            if due_line not in changed_lines:
                changed_lines.append(due_line)
        if rem_dt:
            rem_line = f"🔔 Remind: {rem_dt.strftime('%-d %b %-I:%M %p')}"
            if rem_line not in changed_lines:
                changed_lines.append(rem_line)

        if not changed_lines:
            send_whatsapp_message(phone, "Nothing changed — all fields were the same.\n\nReply *edit* · *reminders*", show_help=False)
        else:
            send_whatsapp_message(
                phone,
                "✅ *Updated!*\n\n" + "\n".join(changed_lines) + "\n\nReply *edit* · *reminders*",
                show_help=False
            )
        clear_state(phone)
        return True

    # ── payment done / payment 1200 / payment 1200 advance 300 ───────────
    if t.startswith("payment") or t.startswith("paid"):
        current = get_reminder_by_id(reminder_id, user_id)
        task    = current.get("task", "") if current else ""

        if "done" in t or "full" in t:
            # Fully paid — get total from existing payment or text
            from repositories.payment_repository import get_payment_for_reminder, update_payment_notify
            existing = get_payment_for_reminder(reminder_id) if reminder_id else None
            total = float(existing["total"]) if existing and existing.get("total") else 0
            if total == 0:
                send_whatsapp_message(phone,
                    "⚠️ No total amount set. Use:\npayment 1200 done", show_help=False)
                return True
            from repositories.payment_repository import create_payment
            create_payment(user_id=user_id, reminder_id=reminder_id,
                           customer=_extract_customer(task),
                           total=total, advance=total, customer_phone=None, notify_customer=False)
            clear_state(phone)
            send_whatsapp_message(phone,
                f"✅ *Payment updated!*\n\n📝 {task}\n💰 Rs.{int(total)} — Fully paid ✅\n\n"
                f"Reply *edit* · *reminders*", show_help=False)
            return True

        total_m   = _re.search(r'\b(?:payment|total|paid)?\s*(\d+)\b', t)
        advance_m = _re.search(r'\b(?:advance|paid)\s+(\d+)\b', t)
        if not total_m:
            send_whatsapp_message(phone,
                "⚠️ Include the amount:\npayment 1200\npayment 1200 advance 300\npayment done",
                show_help=False)
            return True

        total   = float(total_m.group(1))
        advance = float(advance_m.group(1)) if advance_m else 0.0
        advance = min(advance, total)
        balance = total - advance

        from repositories.payment_repository import create_payment
        create_payment(user_id=user_id, reminder_id=reminder_id,
                       customer=_extract_customer(task),
                       total=total, advance=advance, customer_phone=None, notify_customer=False)

        pay_line = (f"💰 Rs.{int(advance)} paid · Rs.{int(balance)} balance due"
                    if balance > 0 else "💰 Fully paid ✅")
        clear_state(phone)
        send_whatsapp_message(phone,
            f"✅ *Payment updated!*\n\n📝 {task}\n{pay_line}\n\nReply *edit* · *reminders*",
            show_help=False)
        return True

    # ── phone 9876543210 ──────────────────────────────────────────────────
    if t.startswith("phone "):
        digits = _re.sub(r'\D', '', text)
        if len(digits) >= 10:
            customer_phone_e164 = '91' + digits[-10:]
            display_num = digits[-10:]
            current = get_reminder_by_id(reminder_id, user_id)
            task = current.get("task", "") if current else ""
            # Get due_at to compute notify time — keep existing reminder untouched
            due_at = current.get("due_at") if current else None
            if due_at and isinstance(due_at, str):
                due_at = datetime.fromisoformat(due_at)
            notify_at, notify_label = _calc_notify_at(due_at)
            from repositories.payment_repository import get_payment_for_reminder, update_payment_notify, create_payment
            existing_pay = get_payment_for_reminder(reminder_id)
            if existing_pay:
                update_payment_notify(existing_pay["id"], customer_phone_e164, notify_at)
            else:
                create_payment(user_id=user_id, reminder_id=reminder_id,
                               customer=_extract_customer(task),
                               total=0, advance=0, customer_phone=customer_phone_e164,
                               notify_customer=True, customer_notify_at=notify_at)
            clear_state(phone)
            send_whatsapp_message(phone,
                f"✅ *Updated!*\n\n📞 {display_num} added\n📲 Notified: {notify_label}\n\nReply *edit* · *reminders*",
                show_help=False)
        else:
            send_whatsapp_message(phone, "⚠️ Send a valid 10-digit number:\nphone 9876543210",
                                  show_help=False)
        return True

    # ── note <special instructions> ──────────────────────────────────────
    if t.startswith("note "):
        note_text = text[5:].strip()
        current   = get_reminder_by_id(reminder_id, user_id)
        if current and note_text:
            # Append note to task with separator
            base_task = (current.get("task") or "").split(" 📌 ")[0].strip()
            new_task  = f"{base_task} 📌 {note_text}"
            due_at    = current.get("due_at") or current.get("reminder_time")
            if due_at and isinstance(due_at, str):
                from datetime import datetime as _dt
                due_at = _dt.fromisoformat(due_at)
            update_reminder(reminder_id, user_id, new_task, None)
            clear_state(phone)
            send_whatsapp_message(phone,
                f"✅ Note saved!\n\n📝 {base_task}\n📌 {note_text}\n\nReply *edit* · *reminders*",
                show_help=False)
        return True

    # ── task <new name> ───────────────────────────────────────────────────
    if t.startswith("task "):
        new_task = text[5:].strip()
        current  = get_reminder_by_id(reminder_id, user_id)
        if current and new_task:
            due_at = current.get("due_at") or current.get("reminder_time")
            if due_at and isinstance(due_at, str):
                from datetime import datetime as _dt
                due_at = _dt.fromisoformat(due_at)
            rem_dt = _default_reminder_time(due_at) if due_at else None
            update_reminder(reminder_id, user_id, new_task, rem_dt)
            clear_state(phone)
            send_whatsapp_message(phone,
                f"✅ Task updated: {new_task}\n\nReply *edit* · *reminders*", show_help=False)
        return True

    # ── date <new date/time> ──────────────────────────────────────────────
    if t.startswith("date "):
        date_text = text[5:].strip()
        extracted = extract_reminder_details(date_text, phone)
        due_date  = extracted.get("date")
        due_time  = extracted.get("time") or "09:00"
        if not due_date:
            send_whatsapp_message(phone,
                "⚠️ Couldn't read that date.\nTry: date 15 Apr 6pm", show_help=False)
            return True
        current = get_reminder_by_id(reminder_id, user_id)
        task    = current.get("task", "") if current else ""
        due_dt  = _build_due_datetime(due_date, due_time)
        rem_dt  = _default_reminder_time(due_dt)
        update_reminder(reminder_id, user_id, task, rem_dt, due_date, due_time)
        clear_state(phone)
        send_whatsapp_message(phone,
            f"✅ *Date updated!*\n\n📝 {task}\n"
            f"📅 Due: {due_dt.strftime('%-d %b %I:%M %p')}\n"
            f"🔔 Remind: {rem_dt.strftime('%-d %b %I:%M %p')}\n\nReply *edit* · *reminders*",
            show_help=False)
        return True

    # ── Full message fallback (old format: "Anjali cake 15 Apr 6pm") ─────
    extracted = extract_reminder_details(text, phone)
    due_date  = extracted.get("date")
    due_time  = extracted.get("time") or "09:00"
    task      = extracted.get("task") or text.strip()

    if not due_date:
        send_whatsapp_message(
            phone,
            "⚠️ I didn't understand that.\n\n"
            "Update one field at a time:\n"
            "task Meena blouse\n"
            "date 15 Apr 6pm\n"
            "payment 1200 advance 300\n"
            "payment done\n"
            "phone 9876543210",
            show_help=False
        )
        return True

    due_dt      = _build_due_datetime(due_date, due_time)
    reminder_dt = _default_reminder_time(due_dt)
    update_reminder(reminder_id, user_id, task, reminder_dt, due_date, due_time)

    total   = extracted.get("total")
    advance = extracted.get("advance") or 0
    if total:
        from repositories.payment_repository import create_payment
        create_payment(user_id=user_id, reminder_id=reminder_id,
                       customer=_extract_customer(task),
                       total=float(total), advance=float(advance),
                       customer_phone=None, notify_customer=False)

    clear_state(phone)
    send_whatsapp_message(
        phone,
        f"✅ *Updated!*\n\n"
        f"📝 {task}\n"
        f"📅 Due: {due_dt.strftime('%-d %b %I:%M %p')}\n"
        f"🔔 Remind: {reminder_dt.strftime('%-d %b %I:%M %p')}\n\n"
        f"Reply *edit* · *reminders*",
        show_help=False
    )
    return True



# Commands and prefixes that should always escape a pending-order state.
# These are messages the user clearly intends as commands, not order content.
_ESCAPE_COMMANDS = {
    "help", "reminders", "list", "unpaid", "pending", "earnings", "income",
    "menu", "commands", "skip", "reset", "stop", "quit", "exit", "new",
    "done", "paid", "find", "edit", "update", "change", "track", "remove",
}
_ESCAPE_PREFIXES = (
    "help ", "paid ", "done ", "find ", "remind ", "delete ",
    "track ", "remove ", "earnings ", "income ",
)

# Steps that should bail immediately when the user sends a command-like message.
# Covers all steps — edit/help/reminders etc. always escape any pending flow.
_ESCAPABLE_STEPS = {
    "awaiting_template", "awaiting_time", "awaiting_task_confirm",
    "awaiting_reminder_time", "awaiting_payment", "awaiting_advance",
    "awaiting_notify_customer", "awaiting_notify_time",
    "awaiting_payment_notify", "awaiting_payment_notify_time",
}


def handle_reminder_state(user_id: str, phone: str, text: str, state: dict) -> bool:
    step = state.get("step")

    # ── Global escape hatch for early-flow steps ──────────────────────────
    # If the user sends a real command while stuck in a template/time prompt,
    # clear state and let route_intent handle it as a fresh message.
    if step in _ESCAPABLE_STEPS:
        t_lower = text.strip().lower()
        if t_lower in _ESCAPE_COMMANDS or any(t_lower.startswith(p) for p in _ESCAPE_PREFIXES):
            clear_state(phone)
            send_whatsapp_message(
                phone,
                "👍 Previous order draft cleared.",
                show_help=False
            )
            return False  # fall through to route_intent

    if step == "awaiting_confirm":
        return _handle_awaiting_confirm(user_id, phone, text, state)

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

    if step == "awaiting_notify_time":
        return _handle_awaiting_notify_time(user_id, phone, text, state)

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

def _send_template(phone: str, task: str, customer_phone=None, total=None, advance=None, date_val: str = ""):
    """Send a copy-paste-friendly template. Known fields are pre-filled; missing ones left blank."""
    task_line     = f"Task: {task.strip()}" if task else "Task: "
    date_line     = f"Date: {date_val}" if date_val else "Date: "
    reminder_line = "Reminder: 2hrs before"
    phone_line    = f"Customer Phone (to notify them): {customer_phone}" if customer_phone else "Customer Phone (to notify them): "
    total_line    = f"Total: {int(total)}" if total is not None else "Total: "
    advance_line  = f"Advance: {int(advance)}" if advance is not None else "Advance: "

    set_state(phone, {
        "step": "awaiting_template",
        "task": task,
        "customer_phone": customer_phone,
        "total": total,
        "advance": advance
    })

    send_whatsapp_message(
        phone,
        f"📋 Copy, fill in the blanks and send back:\n\n"
        f"{task_line}\n"
        f"{date_line}\n"
        f"{reminder_line}\n"
        f"{phone_line}\n"
        f"{total_line}\n"
        f"{advance_line}",
        show_help=False
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
                "⚠️ I couldn't read the date. Try formats like: today, tomorrow, 14 Apr, next Sunday, in 3 days"
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
            "⚠️ I couldn't read the date. Try formats like: today, tomorrow, 14 Apr, next Sunday, in 3 days"
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
            "tomorrow at 6pm  or  13th April 3pm"
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

    save_result = _save_reminder_with_due(user_id, task, reminder_dt, due_date, due_time)
    if not save_result:
        clear_state(phone)
        send_whatsapp_message(
            phone,
            "⚠️ A booking for that task and date already exists — not saved again.\n\n"
            "Send *bookings* to see your list, or save a new order with a different date.",
            show_help=False
        )
        return True

    reminder_id, booking_ref = save_result
    reminder_display = reminder_dt.strftime('%d %b %Y %I:%M %p')
    ref_tag = f"Booking *#{booking_ref}*\n"

    # If we already have total → save payment and finish
    if total is not None:
        customer   = _extract_customer(task)
        adv_amount = min(float(advance or 0), float(total))
        balance    = float(total) - adv_amount
        # Auto-set 7 AM customer notification
        due_dt_for_notify = None
        due_date_s = state.get("due_date")
        due_time_s = state.get("due_time", "12:00")
        if due_date_s:
            due_dt_for_notify = _build_datetime(due_date_s, due_time_s)
        notify_at_rt, notify_label_rt = _calc_notify_at(due_dt_for_notify)
        create_payment(
            user_id=user_id, reminder_id=reminder_id, customer=customer,
            total=float(total), advance=adv_amount, customer_phone=customer_phone,
            notify_customer=bool(customer_phone), customer_notify_at=notify_at_rt if customer_phone else None
        )
        clear_state(phone)
        payment_line = (
            f"💰 Rs.{adv_amount:.0f} advance  ·  Rs.{balance:.0f} balance pending"
            if balance > 0 else "💰 Fully paid ✅"
        )
        display_num = customer_phone[-10:] if customer_phone and len(customer_phone) >= 10 else customer_phone
        notify_line  = f"\n📲 {display_num} notified: {notify_label_rt}" if customer_phone and notify_at_rt else ""
        preview_line = ""
        if customer_phone and notify_at_rt:
            preview_line = f"\n\n📨 *Message {display_num} will receive:*\n{_customer_msg_preview(phone, task, due_dt_for_notify, balance)}"
        send_whatsapp_message(
            phone,
            f"✅ *All saved!* {ref_tag}\n"
            f"📝 {task}\n📅 Due: {due_display}\n"
            f"⏰ Reminder: {reminder_display}\n{payment_line}{notify_line}{preview_line}\n\n"
            f"Reply *unpaid* to see pending balances."
        )
        return True

    # Otherwise continue to customer phone step (skip if already known)
    if customer_phone:
        set_state(phone, {
            "step": "awaiting_payment", "task": task, "due_display": due_display,
            "reminder_id": reminder_id, "booking_ref": booking_ref,
            "reminder_display": reminder_display,
            "customer_phone": customer_phone
        })
        send_whatsapp_message(
            phone,
            f"✅ {ref_tag}\n"
            f"💰 What's the total order amount?\n\n"
            f"Reply with amount e.g. *850*  ·  or *skip*"
        )
    else:
        set_state(phone, {
            "step":             "awaiting_customer_phone",
            "task":             task,
            "due_display":      due_display,
            "reminder_id":      reminder_id,
            "booking_ref":      booking_ref,
            "reminder_display": reminder_display
        })
        send_whatsapp_message(
            phone,
            f"✅ {ref_tag}\n"
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

    notify_line  = ""
    preview_line = ""
    if notify_customer and customer_notify_at:
        display_num_adv = (state.get("customer_phone") or "")[-10:]
        notify_line = f"\n📲 {display_num_adv} notified: {customer_notify_at.strftime('%-d %b at %-I:%M %p')}"
        due_date_s  = state.get("due_date")
        due_time_s  = state.get("due_time", "12:00")
        due_dt_adv  = _build_datetime(due_date_s, due_time_s) if due_date_s else None
        preview     = _customer_msg_preview(phone, task, due_dt_adv, balance)
        preview_line = f"\n\n📨 *Message {display_num_adv} will receive:*\n{preview}"

    send_whatsapp_message(
        phone,
        f"✅ *All saved!*\n\n"
        f"📝 {task}\n"
        f"📅 Due: {due_display}\n"
        f"⏰ Your reminder: {reminder_disp}{notify_line}\n"
        f"{payment_line}{preview_line}\n\n"
        f"Reply *unpaid* anytime to see pending balances."
    )
    return True


def _get_business_name(vendor_phone: str) -> str:
    """Get vendor's business name for customer message preview."""
    try:
        from repositories.user_repository import get_or_create_user
        user = get_or_create_user(vendor_phone)
        return user.get("business_name") or "your vendor"
    except Exception:
        return "your vendor"


def _customer_msg_preview(vendor_phone: str, task: str, due_dt, balance: float = 0) -> str:
    """Build a preview of the WhatsApp message the customer will receive."""
    business_name = _get_business_name(vendor_phone)
    time_str = ""
    if due_dt:
        time_str = due_dt.strftime("%-I:%M %p") if due_dt.minute != 0 else due_dt.strftime("%-I %p")
    time_line  = f"\n⏰ *Today at {time_str}*" if time_str else ""
    bal_line   = f"\n💰 *Balance due: Rs.{balance:.0f}*" if balance > 0 else ""
    return (
        f"Hi! 👋\n"
        f"Heads up! Your order from *{business_name}* is scheduled for *today*."
        f"{time_line}{bal_line}\n"
        f"Have a great day! 😊"
    )


def _calc_notify_at(due_dt) -> tuple:
    """Return (notify_at, notify_label) — auto 7 AM on due date with fallbacks."""
    if not due_dt:
        return None, ""
    from datetime import timezone, timedelta as _td
    IST = timezone(_td(hours=5, minutes=30))
    now_ist      = datetime.now(IST).replace(tzinfo=None)
    seven_am     = due_dt.replace(hour=7, minute=0, second=0, microsecond=0)
    one_hr_before = due_dt - _td(hours=1)
    if seven_am > now_ist:
        return seven_am, seven_am.strftime("%-d %b at 7:00 AM")
    if one_hr_before > now_ist:
        return one_hr_before, one_hr_before.strftime("%-d %b at %-I:%M %p") + " (1 hr before)"
    fallback = now_ist + _td(minutes=2)
    return fallback, "in a few minutes"


def _ask_notify_customer(phone: str, state: dict, preset_option=None):
    """
    Auto-set customer notification to 7 AM on the due date (no question asked).
    Then proceed to payment step (or save directly if total is already known).
    """
    customer_phone   = state.get("customer_phone", "")
    display_num      = customer_phone[-10:] if len(customer_phone) >= 10 else customer_phone
    task             = state.get("task", "")
    total            = state.get("total")
    advance          = state.get("advance")
    reminder_id      = state.get("reminder_id")
    reminder_display = state.get("reminder_display", "")
    reminder_label   = state.get("reminder_label", "")
    user_id          = state.get("user_id", phone)
    due_display      = state.get("due_display", "")

    # Reconstruct due_dt from state
    due_dt = None
    due_dt_str = state.get("due_dt")
    if due_dt_str:
        try:
            due_dt = datetime.fromisoformat(due_dt_str)
        except Exception:
            pass
    if not due_dt:
        due_date_s = state.get("due_date")
        due_time_s = state.get("due_time", "12:00")
        if due_date_s:
            due_dt = _build_datetime(due_date_s, due_time_s)

    notify_at, notify_label = _calc_notify_at(due_dt)
    label_str    = f" {reminder_label}" if reminder_label else " (2 hrs before)"

    # If both 7 AM and 1-hr-before have passed, don't silently book "in a few minutes" —
    # ask the vendor when (or if) they want to notify the customer.
    if notify_label == "in a few minutes":
        set_state(phone, {**state, "step": "awaiting_notify_time"})
        send_whatsapp_message(
            phone,
            f"⏰ *When should we notify {display_num}?*\n\n"
            f"The usual times (7 AM and 1 hr before) have already passed.\n\n"
            f"Reply with a time e.g. *now* · *8pm* · or *skip*",
            show_help=False
        )
        return

    notify_line  = f"\n📲 {display_num} notified: {notify_label}" if notify_at else ""

    booking_ref = state.get("booking_ref")
    ref_tag = f"Booking *#{booking_ref}*\n" if booking_ref else ""

    if total is not None:
        # Total known → save payment and finish immediately
        adv_amount = min(float(advance or 0), float(total))
        balance    = float(total) - adv_amount
        create_payment(
            user_id=user_id, reminder_id=reminder_id, customer=_extract_customer(task),
            total=float(total), advance=adv_amount,
            customer_phone=customer_phone, notify_customer=True, customer_notify_at=notify_at
        )
        set_state(phone, {"step": "just_saved", "reminder_id": reminder_id})
        payment_line = (
            f"💰 Rs.{adv_amount:.0f} advance  ·  Rs.{balance:.0f} balance pending"
            if balance > 0 else "💰 Fully paid ✅"
        )
        preview = _customer_msg_preview(phone, task, due_dt, balance)
        send_whatsapp_message(
            phone,
            f"✅ *All saved!* {ref_tag}\n"
            f"📝 {task}\n"
            f"📅 Due: {due_display}\n"
            f"⏰ Reminder: {reminder_display}{label_str}"
            f"{notify_line}\n\n"
            f"{payment_line}\n\n"
            f"📨 *Message {display_num} will receive:*\n{preview}\n\n"
            f"Reply *unpaid* to see pending balances",
            show_help=False
        )
    else:
        # No total yet — go to payment step with notify_at already set
        set_state(phone, {
            **state,
            "step":               "awaiting_payment",
            "notify_customer":    True,
            "customer_notify_at": notify_at.isoformat() if notify_at else None,
        })
        preview = _customer_msg_preview(phone, task, due_dt, 0)
        send_whatsapp_message(
            phone,
            f"✅ Booking saved! {ref_tag}\n"
            f"📝 {task}\n"
            f"📅 Due: {due_display}\n"
            f"⏰ Reminder: {reminder_display}{label_str}"
            f"{notify_line}\n\n"
            f"📨 *Message {display_num} will receive:*\n{preview}\n\n"
            f"💰 What's the total order amount?\n"
            f"Reply with amount e.g. *850*  ·  or *skip*",
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
            f"💡 Next time try a time like 4pm — I'll WhatsApp them automatically "
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
                    "Type a date & time e.g. 12 Apr 3pm  ·  or *no* to skip",
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
        # Reconstruct due_dt for preview
        due_dt_prev = None
        due_date_s  = state.get("due_date")
        due_time_s  = state.get("due_time", "12:00")
        if due_date_s:
            due_dt_prev = _build_datetime(due_date_s, due_time_s)
        preview_block = ""
        if notify_customer and notify_label and customer_phone:
            preview = _customer_msg_preview(phone, task, due_dt_prev, balance)
            preview_block = f"\n\n📨 *Message {display_num} will receive:*\n{preview}"
        send_whatsapp_message(
            phone,
            f"✅ *All saved!*\n\n"
            f"📝 {task}\n"
            f"📅 Due: {due_display}\n"
            f"⏰ Your reminder: {reminder_disp}\n"
            f"{notify_line}\n"
            f"{payment_line}{preview_block}\n\n"
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


def _handle_awaiting_notify_time(user_id: str, phone: str, text: str, state: dict) -> bool:
    """Vendor replied with preferred customer notify time (or 'skip') after all auto-slots passed."""
    import re as _re2
    t = text.strip().lower()

    customer_phone = state.get("customer_phone", "")
    display_num    = customer_phone[-10:] if len(customer_phone) >= 10 else customer_phone
    task           = state.get("task", "")
    total          = state.get("total")
    advance        = state.get("advance")
    reminder_id    = state.get("reminder_id")
    due_display    = state.get("due_display", "")
    reminder_disp  = state.get("reminder_display", "")
    reminder_label = state.get("reminder_label", "")
    label_str      = f" {reminder_label}" if reminder_label else " (2 hrs before)"

    skip_words = ("skip", "no", "nahi", "na", "nope", "n")
    notify_customer    = True
    customer_notify_at = None
    notify_label       = ""

    if t in skip_words:
        notify_customer = False
        send_whatsapp_message(
            phone,
            f"📵 Skipped — *{display_num}* won't be notified.\n\n"
            f"💡 Next time try a time like *4pm* and I'll WhatsApp them automatically.",
            show_help=False
        )
    elif t == "now":
        from datetime import timezone, timedelta as _td2
        IST = timezone(_td2(hours=5, minutes=30))
        customer_notify_at = datetime.now(IST).replace(tzinfo=None) + _td2(minutes=2)
        notify_label = "in a few minutes"
    else:
        # Parse free-form time e.g. "8pm", "7:30 pm", "tomorrow 9am"
        try:
            from parser.extractors.datetime_extractor import extract_datetime
            parsed = extract_datetime(text)
            if parsed.get("date") or parsed.get("time"):
                cdate = parsed.get("date") or state.get("due_date")
                ctime = parsed.get("time") or "09:00"
                customer_notify_at = _build_datetime(cdate, ctime)
                notify_label = customer_notify_at.strftime('%-d %b at %-I:%M %p')
            else:
                send_whatsapp_message(
                    phone,
                    "⚠️ I couldn't read that time.\n\nTry *now* · *8pm* · or *skip*",
                    show_help=False
                )
                return True
        except Exception:
            send_whatsapp_message(
                phone,
                "⚠️ I couldn't read that time.\n\nTry *now* · *8pm* · or *skip*",
                show_help=False
            )
            return True

    notify_line = (
        f"📲 {display_num} notified: {notify_label}"
        if notify_customer and notify_label
        else "📵 No customer notification"
    )

    # Reconstruct due_dt for preview / payment
    due_dt_prev = None
    due_date_s  = state.get("due_date")
    due_time_s  = state.get("due_time", "12:00")
    if due_date_s:
        due_dt_prev = _build_datetime(due_date_s, due_time_s)

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
        preview_block = ""
        if notify_customer and notify_label and customer_phone:
            preview = _customer_msg_preview(phone, task, due_dt_prev, balance)
            preview_block = f"\n\n📨 *Message {display_num} will receive:*\n{preview}"
        send_whatsapp_message(
            phone,
            f"✅ *All saved!*\n\n"
            f"📝 {task}\n"
            f"📅 Due: {due_display}\n"
            f"⏰ Reminder: {reminder_disp}{label_str}\n"
            f"{notify_line}\n"
            f"{payment_line}{preview_block}\n\n"
            f"Reply *unpaid* to see pending balances",
            show_help=False
        )
        return True

    # No total yet — proceed to payment step
    set_state(phone, {
        **state,
        "step":               "awaiting_payment",
        "notify_customer":    notify_customer,
        "customer_notify_at": customer_notify_at.isoformat() if customer_notify_at else None,
        "customer_phone":     customer_phone if notify_customer else None,
    })
    send_whatsapp_message(
        phone,
        f"💰 What's the total order amount?\n\nReply with amount e.g. *850*  ·  or *skip*"
    )
    return True


# --------------------------------------------------
# Helpers
def _handle_awaiting_payment_notify(user_id: str, phone: str, text: str, state: dict) -> bool:
    """Vendor replied with a phone number (or skip) after adding payment details."""
    t = text.strip()
    if t.lower() in ("skip", "no", "nahi", "na", "done"):
        clear_state(phone)
        msg = "Done 👍  Reply *unpaid* to see pending balances." if state.get("payment_id") else "Done 👍  Reply *reminders* to see your orders."
        send_whatsapp_message(phone, msg, show_help=False)
        return True

    customer_phone = _parse_phone(t)
    if not customer_phone:
        send_whatsapp_message(
            phone,
            "⚠️ Please send a valid 10-digit number e.g. 98XXXXXX10\nor *skip* to continue.",
            show_help=False
        )
        return True

    due_date = state.get("due_date")
    due_time = state.get("due_time", "12:00")
    due_dt   = _build_datetime(due_date, due_time) if due_date else None
    display_num = customer_phone[-10:]

    # Auto-set customer notification to 7 AM on the due date.
    # If 7 AM has already passed (same-day order), fall back to 1 hr before due.
    # If that's also passed, notify immediately (in ~1 min).
    notify_at = None
    notify_label = ""
    if due_dt:
        from datetime import timezone, timedelta as _td
        IST = timezone(_td(hours=5, minutes=30))
        now_ist = datetime.now(IST).replace(tzinfo=None)  # naive IST

        seven_am = due_dt.replace(hour=7, minute=0, second=0, microsecond=0)
        one_hr_before = due_dt - _td(hours=1)

        if seven_am > now_ist:
            notify_at    = seven_am
            notify_label = notify_at.strftime("%-d %b at 7:00 AM")
        elif one_hr_before > now_ist:
            notify_at    = one_hr_before
            notify_label = notify_at.strftime("%-d %b at %-I:%M %p") + " (1 hr before)"
        else:
            # Due time is very soon — send immediately
            notify_at    = now_ist + _td(minutes=2)
            notify_label = "in a few minutes"

    payment_id     = state.get("payment_id")
    reminder_id    = state.get("reminder_id")
    task           = state.get("task", "")

    from repositories.payment_repository import update_payment_notify, create_payment, get_payment_for_reminder
    if payment_id and notify_at:
        update_payment_notify(payment_id, customer_phone, notify_at)
    elif notify_at:
        existing = get_payment_for_reminder(reminder_id) if reminder_id else None
        if existing:
            update_payment_notify(existing["id"], customer_phone, notify_at)
        else:
            customer = _extract_customer(task)
            create_payment(
                user_id=user_id, reminder_id=reminder_id, customer=customer,
                total=0, advance=0, customer_phone=customer_phone,
                notify_customer=True, customer_notify_at=notify_at
            )

    # Build the full saved summary
    due_display  = due_dt.strftime("%-d %b, %-I:%M %p") if due_dt else "—"
    rem_display  = state.get("reminder_display", "")
    task_display = task
    bal_for_preview = 0.0

    lines = [
        f"✅ *All saved!*\n",
        f"📝 {task_display}",
        f"📅 Due: {due_display}",
    ]
    if rem_display:
        lines.append(f"⏰ Your reminder: {rem_display}")
    if notify_at:
        lines.append(f"📲 {display_num} notified: {notify_label}")

    # Payment line
    pay_id = payment_id or (existing["id"] if (existing := (get_payment_for_reminder(reminder_id) if reminder_id else None)) else None)
    if pay_id:
        from repositories.payment_repository import get_payment_by_id
        pay = get_payment_by_id(pay_id) if hasattr(__import__('repositories.payment_repository', fromlist=['get_payment_by_id']), 'get_payment_by_id') else None
        if pay and pay.get("total") and float(pay["total"]) > 0:
            bal_for_preview = float(pay["total"]) - float(pay.get("advance") or 0)
            if bal_for_preview <= 0:
                lines.append("💰 Fully paid ✅")
            else:
                lines.append(f"💰 Rs.{float(pay.get('advance') or 0):.0f} paid · Rs.{bal_for_preview:.0f} balance due")

    # Customer message preview
    if notify_at:
        preview = _customer_msg_preview(phone, task_display, due_dt, bal_for_preview)
        lines.append(f"\n📨 *Message {display_num} will receive:*\n{preview}")

    lines.append(f"\nReply *edit* · *reminders* · unpaid")
    clear_state(phone)
    send_whatsapp_message(phone, "\n".join(lines), show_help=False)
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

    # Parse notification time — accepts:
    #   "1pm", "10:30am", "6:25pm"          — time only → use due date
    #   "2nd april 6:25pm", "Apr 2 6pm"     — date+time → use that specific datetime
    #   "6:25", "18:30"                      — 24-hour or bare time → infer date from due_dt
    notify_at = None

    from parser.extractors.datetime_extractor import extract_datetime, detect_time, parse_time_string
    from ai_extractor import _normalise_text

    from datetime import datetime as _dt, date as _date
    dt_result = extract_datetime(_normalise_text(t))
    got_date = dt_result.get("date")
    got_time = dt_result.get("time")

    # Only treat got_date as a specific date if it's genuinely different from today.
    # "today at 6pm" → got_date=today — user just means the time, apply to due_dt.
    today_iso = _date.today().isoformat()
    specific_date = got_date and got_date != today_iso

    if got_time:
        if specific_date:
            # User gave a specific date+time (e.g. "2nd april 6:25pm")
            notify_at = _dt.fromisoformat(f"{got_date} {got_time}:00")
        elif due_dt:
            # Time only (or "today at Xpm") — apply to due date
            hour, minute = int(got_time[:2]), int(got_time[3:])
            notify_at = due_dt.replace(hour=hour, minute=minute, second=0, microsecond=0)
    else:
        # Last resort: bare 24-hour time like "6:25" with no am/pm
        bare = _re.search(r'\b(\d{1,2}):(\d{2})\b', t)
        if bare and due_dt:
            hour, minute = int(bare.group(1)), int(bare.group(2))
            if 0 <= hour <= 23 and 0 <= minute <= 59:
                notify_at = due_dt.replace(hour=hour, minute=minute, second=0, microsecond=0)

    if not notify_at:
        send_whatsapp_message(
            phone,
            "⚠️ Couldn't read that time. Try 1pm, 10:30am, or 2 Apr 6pm\nor *no* to skip.",
            show_help=False
        )
        return True

    from repositories.payment_repository import update_payment_notify, create_payment, get_payment_for_reminder
    if payment_id:
        update_payment_notify(payment_id, customer_phone, notify_at)
    else:
        # No payment record yet — create a minimal one just to store the notification
        reminder_id = state.get("reminder_id")
        customer    = _extract_customer(state.get("task", ""))
        create_payment(
            user_id=user_id, reminder_id=reminder_id, customer=customer,
            total=0, advance=0, customer_phone=customer_phone,
            notify_customer=True, customer_notify_at=notify_at
        )

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

    display_num_t = customer_phone[-10:] if customer_phone and len(customer_phone) >= 10 else customer_phone or ""
    balance_for_preview = float(payment.get("balance") or 0) if payment else 0
    preview = _customer_msg_preview(phone, task, due_dt, balance_for_preview)
    clear_state(phone)
    send_whatsapp_message(
        phone,
        f"✅ *All saved!*\n\n"
        f"📝 {task}\n"
        f"📅 Due: {due_display}\n"
        f"⏰ Your reminder: {reminder_display}\n"
        f"📲 {display_num_t} notified: {notify_at.strftime('%-d %b at %-I:%M %p')}\n"
        f"{payment_line}\n\n"
        f"📨 *Message {display_num_t} will receive:*\n{preview}\n\n"
        f"Reply *edit* to update · *unpaid* to see balances",
        show_help=False
    )
    return True


# --------------------------------------------------

def _is_real_task(task: str) -> bool:
    """
    Return True if the task contains at least one real word.
    Real words have:
      - Max consecutive consonant run ≤ 4  (gibberish like "sjkjsnkj" has 10+)
      - Vowel ratio ≥ 10%  (real English averages ~38%)
    Vowels include 'y' to handle words like "rhythm", "gym".
    """
    import re
    VOWELS = set('aeiouyAEIOUY')
    CONSONANTS = set('bcdfghjklmnpqrstvwxzBCDFGHJKLMNPQRSTVWXZ')

    words = re.findall(r'[a-zA-Z]{3,}', task)
    if not words:
        return False

    for word in words:
        # Max consecutive consonant run
        max_run = cur_run = 0
        for ch in word:
            if ch in CONSONANTS:
                cur_run += 1
                max_run = max(max_run, cur_run)
            else:
                cur_run = 0

        vowel_ratio = sum(1 for ch in word if ch in VOWELS) / len(word)

        if max_run <= 4 and vowel_ratio >= 0.10:
            return True   # Found at least one real-looking word

    return False


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
    import re, unicodedata
    # Normalize unicode (handles non-breaking spaces, WhatsApp formatting chars, etc.)
    text = unicodedata.normalize("NFKC", text)
    digits = re.sub(r'\D', '', text)
    if len(digits) == 10 and digits[0] in "6789":
        return "91" + digits
    if len(digits) == 12 and digits.startswith("91") and digits[2] in "6789":
        return digits
    # Handle 11-digit with leading 0 (e.g. 09123456780)
    if len(digits) == 11 and digits[0] == "0" and digits[1] in "6789":
        return "91" + digits[1:]
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
    """Save reminder and return (reminder_id, booking_ref) or None on duplicate/error."""
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
            WITH next_ref AS (
                SELECT COALESCE(MAX(booking_ref), 0) + 1 AS ref_num
                FROM reminders WHERE user_id = %s
            )
            INSERT INTO reminders (user_id, task, reminder_time, due_at, booking_ref)
            SELECT %s, %s, %s, %s, ref_num FROM next_ref
            ON CONFLICT (user_id, task, reminder_time) DO NOTHING
            RETURNING id, booking_ref
            """,
            (user_id, user_id, task, reminder_dt, due_at)
        )
        result = cursor.fetchone()
        conn.commit()
        return (result[0], result[1]) if result else None
    except Exception as e:
        conn.rollback()
        print("ERROR saving reminder:", e)
        return None
    finally:
        cursor.close()
        release_connection(conn)