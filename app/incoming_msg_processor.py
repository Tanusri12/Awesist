"""
Main message processor — extracts message, routes to the right handler.
This file only does routing — all logic lives in handlers/.
"""
from conversation_memory import get_state, set_state, clear_state
from repositories.user_repository import (
    get_or_create_user,
    is_onboarded,
    get_subscription_status,
)
from commands.commands import handle_command
from handlers.onboarding import handle_onboarding
from handlers.reminder_handler import handle_create_reminder, handle_reminder_state
from handlers.payment_handler import handle_unpaid, handle_mark_paid, handle_earnings
from handlers.list_handler import handle_list_reminders, handle_delete_reminder
from whatsapp import send_whatsapp_message

USER_CACHE = {}
EXPIRY_MSG_SENT = {}   # phone -> datetime of last expiry message (rate-limit to 1/hour)

# Unicode ranges for Indian scripts (Devanagari, Bengali, Gurmukhi, Gujarati,
# Oriya, Tamil, Telugu, Kannada, Malayalam, Sinhala)
_INDIC_SCRIPT_RE = __import__("re").compile(
    r"[\u0900-\u0DFF\u0E00-\u0E7F\u1C00-\u1CFF]"
)


def _is_english(text: str) -> bool:
    """Return False if the message contains significant Indic or non-Latin script."""
    return not _INDIC_SCRIPT_RE.search(text)

GREETINGS = ["hi", "hello", "hey", "hii", "helo", "good morning",
             "good evening", "good afternoon", "namaste", "namaskar"]
IGNORED   = ["ok", "okay", "thanks", "thank you", "got it",
             "noted", "sure", "great", "👍", "🙏"]


def get_user_cached(phone: str) -> dict:
    if phone in USER_CACHE:
        return USER_CACHE[phone]
    user = get_or_create_user(phone)
    USER_CACHE[phone] = user
    if len(USER_CACHE) > 5000:
        USER_CACHE.clear()
    return user


def extract_message(data: dict):
    try:
        entry   = data["entry"][0]
        changes = entry["changes"][0]
        value   = changes["value"]
        if "messages" not in value:
            return None
        message = value["messages"][0]
        if message.get("type") != "text":
            return None
        return message["from"], message["text"]["body"].strip()
    except Exception as e:
        print("MESSAGE PARSE ERROR:", e)
        return None


def process_message(data: dict):
    try:
        msg_data = extract_message(data)
        if not msg_data:
            return

        phone, text = msg_data
        print(f"MSG from {phone}: {text}")
        text_lower = text.lower().strip()

        # ── Language gate — English only ───────────────────────────────────
        if not _is_english(text):
            send_whatsapp_message(
                phone,
                "Sorry, I currently only understand English. 🙏\n\n"
                "Please send your message in English — for example:\n"
                "_Priya cake 13th April 5pm_",
                show_help=False
            )
            return

        # ── New user → onboarding ──────────────────────────────────────────
        if not is_onboarded(phone):
            handle_onboarding(phone, text, USER_CACHE)
            return

        user = get_user_cached(phone)

        # ── Subscription gate ──────────────────────────────────────────────
        if text_lower in ("subscribe", "pay", "renew", "subscription"):
            # Explicit subscribe intent — always send payment link directly
            _send_payment_link(phone, user)
            return
        if not _check_subscription(phone, user):
            return   # gate sent a payment link — stop here

        # ── Silently ignore filler messages ───────────────────────────────
        if text_lower in IGNORED:
            return

        # ── Greetings — always respond helpfully, before state check ──────
        if text_lower in GREETINGS:
            state = get_state(phone)
            if state and not state.get("_expired"):
                # Mid-flow — offer to continue or cancel
                task = state.get("task", "an order")
                send_whatsapp_message(
                    phone,
                    f"Hi! 👋\n\n"
                    f"We were in the middle of saving *{task}*.\n\n"
                    f"Want to continue or start fresh?\n\n"
                    f"Reply: *continue*  ·  *cancel*",
                    show_help=False
                )
            else:
                # No active state — show usage guide
                send_whatsapp_message(
                    phone,
                    "Hi! 👋 Here's how to use Awesist:\n\n"
                    "*Save an order or appointment:*\n"
                    "_Send cake to Priya on 13th April at 6pm_\n"
                    "_Meena's bridal appointment tomorrow at 10am_\n\n"
                    "*Check your orders:*\n"
                    "• *reminders* → see all upcoming\n"
                    "• *unpaid* → see pending balances\n\n"
                    "*Mark as collected:*\n"
                    "• *paid Priya*  or  *paid 1*\n\n"
                    "*Track your income:*\n"
                    "• *earnings* → this month's collections\n"
                    "• *earnings last month* → previous month\n\n"
                    "• *how* → see message examples\n"
                    "• *help* → see all commands",
                    show_help=False
                )
            return

        # ── Explicit commands (help, reminders, delete, cancel) ───────────
        if handle_command(phone, text, user):
            return

        # ── Active conversation state ──────────────────────────────────────
        state = get_state(phone)

        if state:
            if state.get("_expired"):
                handle_expired_state(phone, text, state, user)
                return
            if handle_reminder_state(user["id"], phone, text, state):
                return

        # ── Intent routing ─────────────────────────────────────────────────
        route_intent(user["id"], phone, text)

    except Exception as e:
        print("PROCESS ERROR:", e)


# ─────────────────────────────────────────────────────────────────────────────
# Subscription helpers
# ─────────────────────────────────────────────────────────────────────────────

def _send_payment_link(phone: str, user: dict):
    """Send the Razorpay payment link to the user."""
    try:
        from services.subscription_service import get_or_create_payment_link
        name = user.get("business_name") or "there"
        link = get_or_create_payment_link(phone, name)
        send_whatsapp_message(
            phone,
            f"Hi *{name}* 👋\n\n"
            "Subscribe to Awesist for just *₹99/month* — that's less than ₹4 a day!\n\n"
            f"👉 Pay here: {link}\n\n"
            "Your data is safe and will be waiting for you. 🔒",
            show_help=False,
        )
    except Exception as e:
        print(f"PAYMENT LINK ERROR for {phone[:6]}***: {e}")
        send_whatsapp_message(
            phone,
            "Here's how to subscribe to Awesist for ₹99/month — please contact us to complete your payment.",
            show_help=False,
        )


def _check_subscription(phone: str, user: dict) -> bool:
    """
    Returns True  → subscription is OK, let the message through.
    Returns False → expired, payment message sent, block the message.

    Nudge schedule (once per day per milestone, keyed by date so server
    restarts within the same day don't resend):
      7 days → gentle heads-up
      5 days → value stats
      3 days → urgency
      1 day  → final warning
    """
    from datetime import datetime
    status = get_subscription_status(phone)

    if status["status"] == "active":
        return True

    if status["status"] == "trial":
        days_left = status["trial_days_left"]
        today     = datetime.utcnow().date().isoformat()
        nudge_key = f"nudge_{phone}_{days_left}_{today}"
        if days_left in (7, 5, 3, 1) and nudge_key not in USER_CACHE:
            USER_CACHE[nudge_key] = True
            name = user.get("business_name") or "there"
            send_whatsapp_message(phone, _nudge_msg(name, days_left), show_help=False)
        return True

    # status == 'expired'
    _send_expired_message(phone, user, status.get("was_paid", False))
    return False


def _nudge_msg(name: str, days_left: int) -> str:
    """Progressive nudge messages as trial winds down."""
    if days_left == 7:
        return (
            f"👋 Hey *{name}*, just a heads-up — your free trial ends in *7 days*.\n\n"
            "Awesist is just *₹99/month* to keep all your reminders, "
            "payment tracking, and morning summaries going.\n\n"
            "Reply *subscribe* anytime to get your payment link."
        )
    if days_left == 5:
        return (
            f"⏳ *{name}*, your free trial ends in *5 days*.\n\n"
            "Everything you've saved — orders, customer numbers, balances — "
            "stays safe when you subscribe.\n\n"
            "Just *₹99/month* — less than ₹4 a day.\n\n"
            "Reply *subscribe* to get your payment link."
        )
    if days_left == 3:
        return (
            f"⚠️ *{name}*, only *3 days left* on your free trial!\n\n"
            "After that, the bot will pause until you subscribe.\n\n"
            "Keep your reminders running for just *₹99/month*.\n\n"
            "👉 Reply *subscribe* now to get your payment link."
        )
    # 1 day
    return (
        f"🚨 *{name}*, your free trial ends *tomorrow*!\n\n"
        "Subscribe today so your reminders keep firing without any break.\n\n"
        "*₹99/month* — that's it.\n\n"
        "👉 Reply *subscribe* right now to get your payment link."
    )


def _send_expired_message(phone: str, user: dict, was_paid: bool = False):
    """
    Send the expiry message. Full stats message the first time, short
    reminder on subsequent messages (rate-limited to once per hour).
    """
    from datetime import datetime
    from repositories.payment_repository import get_trial_stats

    name    = user.get("business_name") or "there"
    user_id = user.get("id") or phone
    now     = datetime.utcnow()

    # Rate-limit: only send full message once per hour
    last_sent = EXPIRY_MSG_SENT.get(phone)
    if last_sent and (now - last_sent).total_seconds() < 3600:
        # Short nudge instead of the full wall of text
        send_whatsapp_message(
            phone,
            f"Your {'subscription' if was_paid else 'trial'} has ended, *{name}*.\n\n"
            "Reply *subscribe* to get your payment link and continue.",
            show_help=False,
        )
        return

    EXPIRY_MSG_SENT[phone] = now

    # ── Stats block ────────────────────────────────────────────────────────
    try:
        stats = get_trial_stats(user_id)
        stats_lines = []
        if stats["total_reminders"]:
            stats_lines.append(f"📦 *{stats['total_reminders']}* orders/appointments saved")
        if stats["upcoming"]:
            stats_lines.append(f"⏰ *{stats['upcoming']}* upcoming orders waiting for reminders")
        if stats["collected_overall"]:
            stats_lines.append(f"💰 *₹{int(stats['collected_overall'])}* collected overall")
        if stats["pending_balance"]:
            stats_lines.append(f"💸 *₹{int(stats['pending_balance'])}* still to collect from customers")

        roi_line = ""
        if stats["collected_overall"] > 990:
            pct = round((99 / stats["collected_overall"]) * 100, 1)
            roi_line = f"\n_Awesist costs just {pct}% of what you've already collected._"

        stats_block = (
            "\n" + "\n".join(stats_lines) + roi_line + "\n\n"
        ) if stats_lines else "\n\n"
    except Exception as e:
        print(f"STATS ERROR for {phone[:6]}***: {e}")
        stats_block = "\n\n"

    # ── Payment link ───────────────────────────────────────────────────────
    try:
        from services.subscription_service import get_or_create_payment_link
        link      = get_or_create_payment_link(phone, name)
        link_line = f"👉 Pay here: {link}"
    except Exception as e:
        print(f"PAYMENT LINK ERROR for {phone[:6]}***: {e}")
        link_line = "👉 Reply *subscribe* and we'll send you the payment link."

    if was_paid:
        # Subscription lapsed — different, warmer tone
        send_whatsapp_message(
            phone,
            f"Hi *{name}* 👋\n\n"
            f"Your Awesist subscription has expired. All your data is safe — "
            f"just renew to pick up right where you left off.\n\n"
            f"*Your account summary:*\n{stats_block}"
            f"Renew for just *₹99/month* to keep everything going.\n\n"
            f"{link_line}\n\n"
            "Your data is safe and will be waiting for you. 🔒",
            show_help=False,
        )
    else:
        # Trial expired
        send_whatsapp_message(
            phone,
            f"Hi *{name}* 👋\n\n"
            f"Your free trial has ended. Here's what you built:\n{stats_block}"
            f"Keep it all going for just *₹99/month* — less than ₹4 a day!\n\n"
            f"{link_line}\n\n"
            "Your data is safe and will be waiting for you. 🔒",
            show_help=False,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Expired-state recovery (unchanged logic)
# ─────────────────────────────────────────────────────────────────────────────

def handle_expired_state(phone: str, text: str, state: dict, user: dict):
    response = text.lower().strip()

    if response in ["yes", "y", "continue", "haan", "ha", "ok", "okay"]:
        state.pop("_expired", None)
        set_state(phone, state)
        task = state.get("task", "your previous order")
        step = state.get("step", "")
        step_messages = {
            "awaiting_reminder_time": (
                f"When should I remind you about: *{task}*?\n\n"
                f"Reply: *2 hrs before*  ·  *day before*  ·  or a specific time like *1pm*"
            ),
            "awaiting_payment": (
                f"What's the total amount for: *{task}*?\n\n"
                f"Reply with amount e.g. *850*  ·  or *skip*"
            ),
            "awaiting_advance": (
                f"Advance received for: *{task}*?\n\n"
                f"Reply with amount e.g. *300*  ·  *no advance*  ·  *full*"
            ),
            "awaiting_time": (
                f"When is *{task}* due?\n\n"
                f"e.g. _tomorrow at 6pm_  or  _13th April 3pm_"
            ),
        }
        msg = step_messages.get(step, f"Continuing with *{task}*. Reply *cancel* to start fresh.")
        send_whatsapp_message(phone, msg)
        return

    if response in ["no", "n", "nahi", "new", "cancel", "start over", "fresh"]:
        clear_state(phone)
        send_whatsapp_message(
            phone,
            "No problem! Starting fresh. 👍\n\n"
            "Just tell me what you want to remember:\n\n"
            "• _Send cake to Priya on 13th April at 6pm_",
            show_help=False
        )
        return

    # New message — clear old state and process fresh
    clear_state(phone)
    send_whatsapp_message(
        phone,
        "I noticed you had an unfinished reminder from earlier — cleared it. 👍",
        show_help=False
    )
    route_intent(user["id"], phone, text)


# ─────────────────────────────────────────────────────────────────────────────
# Intent router (unchanged logic)
# ─────────────────────────────────────────────────────────────────────────────

def route_intent(user_id: str, phone: str, text: str):
    from parser.parser import classify_intent

    text_lower = text.lower().strip()

    # Earnings / monthly income summary
    _earnings_triggers = {
        "earnings", "income", "monthly", "this month",
        "earnings this month", "income this month",
        "how much i made", "how much did i make",
    }
    if text_lower in _earnings_triggers or (
        text_lower.startswith("earnings") and "last" in text_lower
    ) or (
        text_lower.startswith("income") and "last" in text_lower
    ):
        handle_earnings(user_id, phone, text)
        return

    # Payment commands
    if text_lower in ["unpaid", "who owes", "pending payments", "pending"]:
        handle_unpaid(user_id, phone)
        return

    if text_lower == "paid" or text_lower.startswith("paid "):
        if text_lower == "paid":
            handle_unpaid(user_id, phone)
        else:
            handle_mark_paid(user_id, phone, text)
        return

    # Standard intents
    intent = classify_intent(text)

    if intent == "create_reminder":
        handle_create_reminder(user_id, phone, text)
    elif intent == "list_reminders":
        handle_list_reminders(user_id, phone)
    elif intent == "delete_reminder":
        handle_delete_reminder(user_id, phone, text)
    else:
        send_whatsapp_message(
            phone,
            "🤔 I didn't quite get that.\n\n"
            "Try something like:\n"
            "• _Send cake to Priya on 13th April at 6pm_\n"
            "• *reminders* → see your list\n"
            "• *unpaid* → see pending balances\n"
            "• *earnings* → this month's income\n"
            "• *delete 2* → remove a reminder\n\n"
            "Type *how* to see message examples  ·  *help* for all commands."
        )
