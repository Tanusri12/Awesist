import re
from datetime import datetime, date
from calendar import month_name
from repositories.payment_repository import (
    get_unpaid, mark_paid, get_monthly_earnings, create_payment_only,
    delete_payment_entry, get_pending_summary,
)
from whatsapp import send_whatsapp_message


def handle_unpaid(user_id: str, phone: str):
    unpaid = get_unpaid(user_id)
    if not unpaid:
        send_whatsapp_message(phone, "✅ No pending balances — all payments collected!\n\nReply *earnings* · *help*", show_help=False)
        return
    today = date.today()
    total_pending = sum(float(r["balance"]) for r in unpaid)
    message = "💰 *Pending balances:*\n\n"
    for i, r in enumerate(unpaid, start=1):
        due = r.get("due_at")
        due_str = ""
        overdue = False
        if due:
            if isinstance(due, str):
                due = datetime.fromisoformat(due)
            if due.date() < today:
                due_str = f" · due {due.strftime('%d %b')} ⚠️ Overdue"
                overdue = True
            else:
                due_str = f" · due {due.strftime('%d %b')}"
        customer_name = r['customer'] or r['task']
        message += (
            f"{i}. *{customer_name}*\n"
            f"   Total: Rs.{float(r['total']):.0f}  ·  Paid: Rs.{float(r['advance']):.0f}\n"
            f"   *Balance: Rs.{float(r['balance']):.0f} due*{due_str}\n\n"
        )
    message += f"Total due: *Rs.{total_pending:.0f}*\n\n"
    first_name = (unpaid[0]['customer'] or unpaid[0]['task'] or "customer").split()[0]
    message += f"*paid 1* → mark as received\n"
    message += f"*paid all* → mark all as received\n"
    message += f"*remind 1* → send payment reminder to {first_name}\n"
    message += f"*remove 1* → remove from this list\n\n"
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
        index  = int(arg) - 1
        unpaid = get_unpaid(user_id)
        if index < 0 or index >= len(unpaid):
            send_whatsapp_message(phone, "⚠️ Number not found. Send *unpaid* to see your list.", show_help=False)
            return
        r = unpaid[index]
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

        first_name = customer_name.split()[0].capitalize() if customer_name else "there"
        msg = (
            f"Hi {first_name}! 👋\n\n"
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
        send_whatsapp_message(phone, "⚠️ Send: *remind 2*  (use the number from *unpaid* list)", show_help=False)
        return

    index  = int(parts[1]) - 1
    unpaid = get_unpaid(user_id)
    if index < 0 or index >= len(unpaid):
        send_whatsapp_message(phone, "⚠️ Number not found. Send *unpaid* to see your list.", show_help=False)
        return

    r = unpaid[index]
    customer_phone = r.get("customer_phone")
    if not customer_phone:
        send_whatsapp_message(
            phone,
            f"⚠️ No phone number saved for *{r['customer'] or r['task']}*.\n\n"
            f"Add one via *edit* → phone 9876543210",
            show_help=False
        )
        return

    # Get business name
    try:
        from repositories.user_repository import get_or_create_user
        biz = (get_or_create_user(phone) or {}).get("business_name") or "us"
    except Exception:
        biz = "us"

    customer_name = r["customer"] or r["task"] or "there"
    first_name    = customer_name.split()[0].capitalize()
    balance       = float(r["balance"])

    nudge_msg = (
        f"Hi {first_name}! 👋\n\n"
        f"Just a gentle reminder — a balance of *Rs.{balance:.0f}* is due for your order.\n\n"
        f"Please pay at your earliest convenience. Thank you! 🙏\n\n"
        f"— {biz}"
    )
    send_whatsapp_message(str(customer_phone), nudge_msg, show_help=False)
    display_num = str(customer_phone)[-10:]
    send_whatsapp_message(
        phone,
        f"✅ Payment reminder sent to {display_num}!\n\n"
        f"Message:\n\"{nudge_msg[:80]}...\"\n\n"
        f"Reply *unpaid* · *earnings*",
        show_help=False
    )


def handle_remove_payment(user_id: str, phone: str, text: str):
    parts = text.strip().split()
    if len(parts) < 2 or not parts[1].isdigit():
        send_whatsapp_message(phone, "❌ Send: *remove 2*  (use the number from *unpaid* list)", show_help=False)
        return
    index  = int(parts[1]) - 1
    unpaid = get_unpaid(user_id)
    if index < 0 or index >= len(unpaid):
        send_whatsapp_message(phone, "❌ Entry not found. Send *unpaid* to see your list.", show_help=False)
        return
    r = unpaid[index]
    customer = r["customer"] or r.get("task") or f"#{index + 1}"
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
