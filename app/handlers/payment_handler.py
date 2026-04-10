import re
from datetime import datetime, date
from calendar import month_name
from repositories.payment_repository import (
    get_unpaid, mark_paid, get_monthly_earnings, create_payment_only,
    delete_payment_entry, get_pending_summary, get_notified_payments,
    update_customer_msg_id,
)
from whatsapp import send_whatsapp_message


def _ref_label(r: dict) -> str:
    """Return booking_ref as string if exists, else '' — used for display and commands."""
    ref = r.get("booking_ref")
    return str(ref) if ref else ""


def _find_unpaid_by_ref(unpaid: list, num: int):
    """Look up an unpaid entry by booking_ref first, fall back to list position."""
    # Try booking_ref match
    for r in unpaid:
        if r.get("booking_ref") == num:
            return r
    # Fall back to 1-based list index (for payment-only records with no booking)
    idx = num - 1
    if 0 <= idx < len(unpaid):
        return unpaid[idx]
    return None


def handle_unpaid(user_id: str, phone: str):
    unpaid = get_unpaid(user_id)
    if not unpaid:
        send_whatsapp_message(phone, "✅ No pending balances — all payments collected!\n\nReply *earnings* · *help*", show_help=False)
        return
    today = date.today()
    total_pending = sum(float(r["balance"]) for r in unpaid)
    message = "💰 *Pending balances:*\n\n"
    for i, r in enumerate(unpaid, start=1):
        ref  = _ref_label(r)
        due = r.get("due_at")
        due_str = ""
        if due:
            if isinstance(due, str):
                due = datetime.fromisoformat(due)
            if due.date() < today:
                due_str = f" · due {due.strftime('%d %b')} ⚠️ Overdue"
            else:
                due_str = f" · due {due.strftime('%d %b')}"
        task = r['task'] or r['customer'] or "Order"
        ref_line = f"   Booking Ref: {ref}\n" if ref else ""
        message += (
            f"{i}. *{task}*\n"
            f"{ref_line}"
            f"   Total: Rs.{float(r['total']):.0f}  ·  Paid: Rs.{float(r['advance']):.0f}\n"
            f"   *Balance: Rs.{float(r['balance']):.0f} due*{due_str}\n\n"
        )
    message += f"Total due: *Rs.{total_pending:.0f}*\n\n"
    first_ref = _ref_label(unpaid[0]) or "1"
    message += f"*paid {first_ref}* → mark as received\n"
    message += f"*paid all* → mark all as received\n"
    message += f"*remind {first_ref}* → send payment reminder\n"
    message += f"*remove {first_ref}* → remove from this list\n"
    message += f"*booking {first_ref}* → see full booking details\n\n"
    message += "Reply *earnings* · *help*"
    send_whatsapp_message(phone, message, show_help=False)


def handle_mark_paid(user_id: str, phone: str, text: str):
    from conversation_memory import set_state, clear_state
    parts = text.strip().split(None, 1)
    if len(parts) < 2:
        handle_unpaid(user_id, phone)
        return
    arg = parts[1].strip().lower()

    if arg == "all":
        unpaid = get_unpaid(user_id)
        if not unpaid:
            send_whatsapp_message(phone, "✅ No pending balances to clear.", show_help=False)
            return
        total = sum(float(r["balance"]) for r in unpaid)
        for r in unpaid:
            mark_paid(r["id"], user_id)
        send_whatsapp_message(phone, f"✅ All balances cleared!\n\nRs.{total:.0f} collected. 💰\n\nReply *earnings* · *help*", show_help=False)
        return

    if arg.isdigit():
        unpaid = get_unpaid(user_id)
        r = _find_unpaid_by_ref(unpaid, int(arg))
        if not r:
            send_whatsapp_message(phone, "⚠️ Number not found. Send *unpaid* to see your list.", show_help=False)
            return
        mark_paid(r["id"], user_id)
        customer_name = r["customer"] or r["task"] or "the customer"
        amount = float(r["balance"])

        # Check if we have a customer phone to offer thank-you
        customer_phone_raw = r.get("customer_phone")
        if customer_phone_raw:
            display_num = str(customer_phone_raw)[-10:]
            set_state(phone, {
                "step": "awaiting_thankyou",
                "payment_id": r["id"],
                "customer_phone": str(customer_phone_raw),
                "customer_name": customer_name,
                "task": r.get("task", ""),
                "amount": amount,
            })
            send_whatsapp_message(
                phone,
                f"✅ *Payment collected!*\n\n"
                f"📝 {customer_name}\n"
                f"💰 Rs.{amount:.0f} fully paid\n\n"
                f"👋 Send a thank-you to {display_num}?\n"
                f"Reply *yes* to send  ·  *skip* to skip",
                show_help=False
            )
        else:
            send_whatsapp_message(
                phone,
                f"✅ *Payment collected!*\n\n"
                f"📝 {customer_name}\n"
                f"💰 Rs.{amount:.0f} fully paid\n\n"
                f"Reply *earnings* · *unpaid*",
                show_help=False
            )
        return

    unpaid  = get_unpaid(user_id)
    matches = [r for r in unpaid if arg in (r["customer"] or "").lower()]
    if not matches:
        send_whatsapp_message(phone, f"⚠️ No unpaid order for '{parts[1]}'.\n\nSend *unpaid* to see your list.", show_help=False)
        return
    if len(matches) > 1:
        message = f"Found {len(matches)} orders for '{parts[1]}':\n\n"
        for i, r in enumerate(matches, 1):
            message += f"{i}. {r['customer']} · Rs.{float(r['balance']):.0f} balance\n"
        message += "\nReply with the number to mark as collected."
        send_whatsapp_message(phone, message, show_help=False)
        return
    r = matches[0]
    mark_paid(r["id"], user_id)
    send_whatsapp_message(phone, f"✅ Rs.{float(r['balance']):.0f} collected from *{r['customer']}*. 💰\n\nReply *earnings* · *unpaid*", show_help=False)


def handle_thankyou_reply(user_id: str, phone: str, text: str, state: dict) -> bool:
    """Handle vendor reply to 'send thank-you?' prompt."""
    from conversation_memory import clear_state
    t = text.strip().lower()
    clear_state(phone)

    if t in ("yes", "y", "haan", "ha", "send", "ok"):
        customer_phone = state.get("customer_phone")
        customer_name  = state.get("customer_name", "there")
        task           = state.get("task", "your order")
        amount         = state.get("amount", 0)

        # Get business name
        try:
            from repositories.user_repository import get_or_create_user
            biz = (get_or_create_user(phone) or {}).get("business_name") or "us"
        except Exception:
            biz = "us"

        msg = (
            f"Hi! 👋\n\n"
            f"Payment received for your order. Thank you so much! 🙏\n\n"
            f"— {biz}"
        )
        send_whatsapp_message(customer_phone, msg, show_help=False)
        display_num = str(customer_phone)[-10:]
        send_whatsapp_message(
            phone,
            f"✅ Thank-you sent to {display_num}!\n\nReply *earnings* · *unpaid*",
            show_help=False
        )
    else:
        send_whatsapp_message(phone, "Done 👍\n\nReply *earnings* · *unpaid*", show_help=False)
    return True


def handle_remind_customer(user_id: str, phone: str, text: str):
    """remind <number> — send payment nudge WhatsApp to customer."""
    parts = text.strip().split()
    if len(parts) < 2 or not parts[1].isdigit():
        send_whatsapp_message(phone, "⚠️ Send: *remind #5*  (use the booking # from *unpaid* list)", show_help=False)
        return

    unpaid = get_unpaid(user_id)
    r = _find_unpaid_by_ref(unpaid, int(parts[1]))
    if not r:
        send_whatsapp_message(phone, "⚠️ Number not found. Send *unpaid* to see your list.", show_help=False)
        return
    customer_phone = r.get("customer_phone")
    if not customer_phone:
        ref = r.get("booking_ref")
        send_whatsapp_message(
            phone,
            f"⚠️ No phone number saved for this booking.\n\n"
            f"Add one: *edit {ref}* → then reply: phone 9876543210",
            show_help=False
        )
        return

    # Get business name
    try:
        from repositories.user_repository import get_or_create_user
        biz = (get_or_create_user(phone) or {}).get("business_name") or "us"
    except Exception:
        biz = "us"

    balance = float(r["balance"])

    nudge_msg = (
        f"Hi! 👋\n\n"
        f"Just a gentle reminder — a balance of *Rs.{balance:.0f}* is due for your order.\n\n"
        f"Please pay at your earliest convenience. Thank you! 🙏\n\n"
        f"— {biz}"
    )
    from whatsapp import send_whatsapp_message_tracked
    wamid = send_whatsapp_message_tracked(str(customer_phone), nudge_msg)
    if wamid:
        update_customer_msg_id(r["id"], wamid)

    display_num = str(customer_phone)[-10:]
    send_whatsapp_message(
        phone,
        f"✅ Payment reminder sent to {display_num}!\n\n"
        f"Reply *msgs* to see all client notifications · *unpaid* · *earnings*",
        show_help=False
    )


def handle_client_msgs(user_id: str, phone: str):
    """Show all customer notifications sent by this vendor."""
    rows = get_notified_payments(user_id)
    if not rows:
        send_whatsapp_message(
            phone,
            "✅ No pending client notifications — all notified customers have paid!\n\n"
            "Use *remind #N* to send a payment reminder to a customer.",
            show_help=False
        )
        return

    _STATUS_ICON = {
        "read":      "👀 Seen",
        "delivered": "📩 Received",
        "sent":      "📤 Sent",
    }

    lines = [f"📨 *Client Notifications ({len(rows)})*\n"]
    for i, r in enumerate(rows, start=1):
        ref             = r.get("booking_ref")
        task            = (r.get("task") or r.get("customer") or "Order")
        balance         = float(r.get("balance") or 0)
        pay_status      = r.get("status", "pending")
        msg_status      = r.get("customer_msg_status")
        customer_notified = r.get("customer_notified", False)
        notify_at       = r.get("customer_notify_at")

        bal_str  = f"💰 Rs.{int(balance)} due" if balance > 0 and pay_status != "paid" else "✅ Paid"
        time_str = ""
        if notify_at:
            try:
                if isinstance(notify_at, str):
                    from datetime import datetime as _dt
                    notify_at = _dt.fromisoformat(notify_at)
                time_str = f" · {notify_at.strftime('%-d %b, %-I:%M %p')}"
            except Exception:
                pass
        if not customer_notified:
            delivery = f"⏳ Scheduled{time_str}"
            time_str = ""
        else:
            delivery = _STATUS_ICON.get(msg_status, "📤 Sent")

        ref_str = f"   Booking Ref: {ref}" if ref else ""
        lines.append(f"{i}. {task}{time_str}")
        if ref_str:
            lines.append(ref_str)
        lines.append(f"   {delivery} · {bal_str}")
        lines.append("")

    lines.append("Reply *remind N* to nudge again · *unpaid*")
    send_whatsapp_message(phone, "\n".join(lines), show_help=False)


def handle_remove_payment(user_id: str, phone: str, text: str):
    parts = text.strip().split()
    if len(parts) < 2 or not parts[1].isdigit():
        send_whatsapp_message(phone, "❌ Send: *remove #5*  (use the booking # from *unpaid* list)", show_help=False)
        return
    unpaid = get_unpaid(user_id)
    r = _find_unpaid_by_ref(unpaid, int(parts[1]))
    if not r:
        send_whatsapp_message(phone, "❌ Entry not found. Send *unpaid* to see your list.", show_help=False)
        return
    ref      = _ref_label(r)
    customer = r["customer"] or r.get("task") or ref or "entry"
    delete_payment_entry(r["id"], user_id)
    send_whatsapp_message(
        phone,
        f"✅ Removed *{customer}* (₹{float(r['total']):.0f}) from your unpaid list.",
        show_help=False
    )


def handle_track_payment(user_id: str, phone: str, text: str):
    body = re.sub(r"^track\s+", "", text.strip(), flags=re.IGNORECASE).strip()
    if not body:
        send_whatsapp_message(phone, "❌ Tell me who to track.\n\nExample: *track Anjali total 1200 advance 300*")
        return

    total_match   = re.search(r"\btotal\s+(\d+(?:\.\d+)?)", body, re.IGNORECASE)
    advance_match = re.search(r"\b(?:advance|paid)\s+(\d+(?:\.\d+)?)", body, re.IGNORECASE)
    total   = float(total_match.group(1))   if total_match   else 0.0
    advance = float(advance_match.group(1)) if advance_match else 0.0

    if total == 0:
        send_whatsapp_message(phone, "❌ Please include the total amount.\n\nExample: *track Anjali total 1200 advance 300*")
        return
    if advance > total:
        send_whatsapp_message(phone, "❌ Advance can't be more than the total amount.")
        return

    name_end = re.search(r"\b(?:total|advance|paid|\d{10})\b", body, re.IGNORECASE)
    customer = body[:name_end.start()].strip() if name_end else body.strip()
    customer = re.sub(r"\d{10,}", "", customer).strip()

    if not customer:
        send_whatsapp_message(phone, "❌ I need a customer name.\n\nExample: *track Anjali total 1200 advance 300*")
        return

    create_payment_only(user_id, customer, total, advance)
    balance = total - advance
    if balance > 0:
        msg = (
            f"✅ *Payment tracked — {customer}*\n\n"
            f"💰 Total: Rs.{total:.0f}\n"
            f"✅ Paid: Rs.{advance:.0f}\n"
            f"⏳ Balance due: *Rs.{balance:.0f}*\n\n"
            f"⚠️ No order or reminder created.\n\n"
            "When balance is collected:\n"
            "Send *unpaid* → then *paid 1* (use the number shown)"
        )
    else:
        msg = (
            f"✅ *Payment tracked — {customer}*\n\n"
            f"💰 Rs.{total:.0f} — Fully paid ✅\n\n"
            f"⚠️ No order or reminder created.\n\n"
            "Reply *earnings* to see this month's collections."
        )
    send_whatsapp_message(phone, msg, show_help=False)


def handle_earnings(user_id: str, phone: str, text: str):
    now = date.today()
    text_lower = text.lower().strip()

    if "last month" in text_lower or "last" in text_lower:
        if now.month == 1:
            year, month = now.year - 1, 12
        else:
            year, month = now.year, now.month - 1
    else:
        year, month = now.year, now.month

    label = f"{month_name[month]} {year}"
    data  = get_monthly_earnings(user_id, year, month)

    if data["total"] == 0:
        send_whatsapp_message(
            phone,
            f"📊 *Earnings — {label}*\n\n"
            f"No payments collected in {label}.\n\n"
            "To record a payment: send *unpaid* → then *paid <number>*\n\n"
            "Reply *unpaid* · *help*",
            show_help=False
        )
        return

    avg = data["total"] / data["order_count"] if data["order_count"] else 0

    msg  = f"📊 *Earnings — {label}*\n\n"
    msg += f"💰 *Total collected: ₹{data['total']:.0f}*\n"
    msg += f"📦 Orders completed: {data['order_count']}\n"
    msg += f"📈 Avg per order:    ₹{avg:.0f}\n"

    if data["customers"]:
        msg += "\n*Top customers:*\n"
        for r in data["customers"][:5]:
            msg += f"  · {r['customer']} — ₹{float(r['amount']):.0f}"
            orders = int(r["orders"])
            if orders > 1:
                msg += f" ({orders} orders)"
            msg += "\n"
        if len(data["customers"]) > 5:
            rest = len(data["customers"]) - 5
            msg += f"  + {rest} more customer{'s' if rest > 1 else ''}\n"

    # Still pending
    pending = get_pending_summary(user_id)
    if pending["count"] > 0:
        msg += f"\n💰 Still pending: *Rs.{pending['amount']:.0f}* from {pending['count']} order{'s' if pending['count'] > 1 else ''}"

    if "last month" not in text_lower:
        msg += "\n\nReply *earnings last month* to compare."
    msg += "\n\nReply *unpaid* · *help*"

    send_whatsapp_message(phone, msg, show_help=False)
