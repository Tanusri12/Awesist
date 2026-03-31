import re
from datetime import datetime, date
from calendar import month_name
from repositories.payment_repository import (
    get_unpaid, mark_paid, get_monthly_earnings, create_payment_only,
)
from whatsapp import send_whatsapp_message


def handle_unpaid(user_id: str, phone: str):
    unpaid = get_unpaid(user_id)
    if not unpaid:
        send_whatsapp_message(phone, "✅ No pending balances — all payments collected!")
        return
    total_pending = sum(float(r["balance"]) for r in unpaid)
    message = "💰 *Pending balances:*\n\n"
    for i, r in enumerate(unpaid, start=1):
        due = r.get("due_at")
        due_str = ""
        if due:
            if isinstance(due, str):
                due = datetime.fromisoformat(due)
            due_str = f" · due {due.strftime('%d %b')}"
        message += (
            f"{i}. {r['customer'] or r['task']}\n"
            f"   Total: Rs.{float(r['total']):.0f} · "
            f"Advance: Rs.{float(r['advance']):.0f} · "
            f"*Balance: Rs.{float(r['balance']):.0f}*{due_str}\n\n"
        )
    message += f"Total pending: *Rs.{total_pending:.0f}*\n\n"
    message += "*To mark as collected:*\n"
    for i, r in enumerate(unpaid, start=1):
        customer = r["customer"] or r["task"] or f"#{i}"
        message += f"• *paid {i}* → {customer}\n"
    message += "• *paid all* → clear everything"
    send_whatsapp_message(phone, message)


def handle_mark_paid(user_id: str, phone: str, text: str):
    parts = text.strip().split(None, 1)
    if len(parts) < 2:
        send_whatsapp_message(phone, "⚠️ Send: *paid 2*  or  *paid Anjali*")
        return
    arg = parts[1].strip().lower()

    if arg == "all":
        unpaid = get_unpaid(user_id)
        if not unpaid:
            send_whatsapp_message(phone, "✅ No pending balances to clear.")
            return
        total = sum(float(r["balance"]) for r in unpaid)
        for r in unpaid:
            mark_paid(r["id"], user_id)
        send_whatsapp_message(phone, f"✅ All balances cleared!\n\nRs.{total:.0f} collected. 💰")
        return

    if arg.isdigit():
        index  = int(arg) - 1
        unpaid = get_unpaid(user_id)
        if index < 0 or index >= len(unpaid):
            send_whatsapp_message(phone, "⚠️ Number not found. Send *unpaid* to see your list.")
            return
        r = unpaid[index]
        mark_paid(r["id"], user_id)
        send_whatsapp_message(
            phone,
            f"✅ Rs.{float(r['balance']):.0f} collected from *{r['customer'] or r['task']}*. 💰"
        )
        return

    unpaid  = get_unpaid(user_id)
    matches = [r for r in unpaid if arg in (r["customer"] or "").lower()]
    if not matches:
        send_whatsapp_message(phone, f"⚠️ No unpaid order for '{parts[1]}'.\n\nSend *unpaid* to see your list.")
        return
    if len(matches) > 1:
        message = f"Found {len(matches)} orders for '{parts[1]}':\n\n"
        for i, r in enumerate(matches, 1):
            message += f"{i}. {r['customer']} · Rs.{float(r['balance']):.0f} balance\n"
        message += "\nReply with the number to mark as collected."
        send_whatsapp_message(phone, message)
        return
    r = matches[0]
    mark_paid(r["id"], user_id)
    send_whatsapp_message(phone, f"✅ Rs.{float(r['balance']):.0f} collected from *{r['customer']}*. 💰")


def handle_track_payment(user_id: str, phone: str, text: str):
    """
    Parse: track <name> [total <amount>] [advance <amount>]

    Examples:
      track Anjali total 1200 advance 300
      track Rahul total 800
      track Meena 9876543210 total 500
    """
    # Strip the leading "track" keyword
    body = re.sub(r"^track\s+", "", text.strip(), flags=re.IGNORECASE).strip()

    if not body:
        send_whatsapp_message(
            phone,
            "❌ Tell me who to track.\n\n"
            "Example: *track Anjali total 1200 advance 300*"
        )
        return

    # Extract total
    total_match   = re.search(r"\btotal\s+(\d+(?:\.\d+)?)", body, re.IGNORECASE)
    advance_match = re.search(r"\b(?:advance|paid)\s+(\d+(?:\.\d+)?)", body, re.IGNORECASE)

    total   = float(total_match.group(1))   if total_match   else 0.0
    advance = float(advance_match.group(1)) if advance_match else 0.0

    if total == 0:
        send_whatsapp_message(
            phone,
            "❌ Please include the total amount.\n\n"
            "Example: *track Anjali total 1200 advance 300*"
        )
        return

    if advance > total:
        send_whatsapp_message(phone, "❌ Advance can't be more than the total amount.")
        return

    # Customer name = everything before first keyword (total / advance / paid / phone number)
    name_end = re.search(
        r"\b(?:total|advance|paid|\d{10})\b", body, re.IGNORECASE
    )
    customer = body[:name_end.start()].strip() if name_end else body.strip()
    # Remove any stray phone number from the name
    customer = re.sub(r"\d{10,}", "", customer).strip()

    if not customer:
        send_whatsapp_message(
            phone,
            "❌ I need a customer name.\n\n"
            "Example: *track Anjali total 1200 advance 300*"
        )
        return

    create_payment_only(user_id, customer, total, advance)

    balance = total - advance
    if balance > 0:
        msg = (
            f"✅ *{customer}* — payment tracked!\n\n"
            f"💰 Total: ₹{total:.0f}\n"
            f"✅ Advance: ₹{advance:.0f}\n"
            f"⏳ Balance due: *₹{balance:.0f}*\n\n"
            "When collected:\n"
            "1️⃣ Send *unpaid* to see your list\n"
            "2️⃣ Send *paid 1* (or the number next to their name)"
        )
    else:
        msg = (
            f"✅ *{customer}* — fully paid! ₹{total:.0f} recorded.\n\n"
            "Reply *earnings* to see this month's collections."
        )

    send_whatsapp_message(phone, msg)


def handle_earnings(user_id: str, phone: str, text: str):
    """
    Show monthly earnings summary.
    Supports:
      "earnings"            → current month
      "earnings last month" → previous calendar month
    """
    now = date.today()
    text_lower = text.lower().strip()

    # Determine which month to show
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
        tip = (
            "No payments collected in *" + label + "* yet.\n\n"
            "💡 When a customer pays, send *unpaid* to see your pending list,\n"
            "then reply with the number next to their name to mark it collected.\n\n"
            "Your earnings will appear here once you start marking payments."
        )
        send_whatsapp_message(phone, "📊 *Earnings — " + label + "*\n\n" + tip)
        return

    avg = data["total"] / data["order_count"] if data["order_count"] else 0

    msg  = f"📊 *Earnings — {label}*\n\n"
    msg += f"💰 *Total collected: ₹{data['total']:.0f}*\n"
    msg += f"📦 Orders completed: {data['order_count']}\n"
    msg += f"📈 Avg per order:    ₹{avg:.0f}\n"

    if data["customers"]:
        msg += "\n*Top customers:*\n"
        for r in data["customers"][:5]:
            msg += f"  • {r['customer']} — ₹{float(r['amount']):.0f}"
            orders = int(r["orders"])
            if orders > 1:
                msg += f" ({orders} orders)"
            msg += "\n"
        if len(data["customers"]) > 5:
            rest = len(data["customers"]) - 5
            msg += f"  _+ {rest} more customer{'s' if rest > 1 else ''}_\n"

    # Gentle nudge to mark anything still pending
    msg += "\nReply *unpaid* to see pending balances."
    if "last month" not in text_lower:
        msg += "\nReply *earnings last month* to compare."

    send_whatsapp_message(phone, msg)