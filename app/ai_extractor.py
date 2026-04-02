import json
import re
import time
import requests
from config import OPENAI_API_KEY

OPENAI_URL = "https://api.openai.com/v1/chat/completions"

# Per-plan daily AI call limits
_AI_DAILY_LIMITS = {
    "trial":   5,
    "basic":  15,
    "pro":    999,
}
_AI_COOLDOWN_SECS = 60   # min seconds between two AI calls from the same user


def _ai_rate_check(phone: str, plan: str = "trial") -> tuple:
    """
    Check DB-backed rate limit. Returns (allowed: bool, count: int, last_ts: float).
    Uses ai_rate_limits table — survives restarts, resistant to abuse.
    """
    from datetime import date
    from repositories.db_pool import get_connection, release_connection
    today = date.today().isoformat()
    conn  = get_connection()
    try:
        cur = conn.cursor()
        # Upsert today's row if it doesn't exist
        cur.execute("""
            INSERT INTO ai_rate_limits (user_id, date, count, last_ts)
            VALUES (%s, %s, 0, 0)
            ON CONFLICT (user_id, date) DO NOTHING
        """, (phone, today))
        conn.commit()
        cur.execute(
            "SELECT count, last_ts FROM ai_rate_limits WHERE user_id=%s AND date=%s",
            (phone, today)
        )
        row = cur.fetchone()
        count, last_ts = (row[0], float(row[1])) if row else (0, 0.0)
        return count, last_ts
    except Exception as e:
        print(f"[AI rate check error] {e}")
        return 0, 0.0
    finally:
        cur.close()
        release_connection(conn)


def _ai_allowed(phone: str, plan: str = "trial") -> bool:
    """Return True if this user is allowed another AI call right now."""
    count, last_ts = _ai_rate_check(phone, plan)

    # Per-minute cooldown — stops rapid spamming
    if time.time() - last_ts < _AI_COOLDOWN_SECS:
        return False

    # Daily limit by plan
    limit = _AI_DAILY_LIMITS.get(plan, _AI_DAILY_LIMITS["trial"])
    return count < limit


def _ai_record_call(phone: str):
    """Increment the DB-backed AI call counter for this user."""
    from datetime import date
    from repositories.db_pool import get_connection, release_connection
    today = date.today().isoformat()
    now_ts = time.time()
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO ai_rate_limits (user_id, date, count, last_ts)
            VALUES (%s, %s, 1, %s)
            ON CONFLICT (user_id, date) DO UPDATE
            SET count   = ai_rate_limits.count + 1,
                last_ts = EXCLUDED.last_ts
        """, (phone, today, now_ts))
        conn.commit()
    except Exception as e:
        print(f"[AI record call error] {e}")
    finally:
        cur.close()
        release_connection(conn)


def _looks_like_order(text: str) -> bool:
    """
    Quick filter — return False for messages that are clearly NOT orders.
    Avoids wasting AI tokens on questions, greetings, commands, etc.
    """
    t = text.strip().lower()
    # Too short to be an order
    if len(t.split()) < 3:
        return False
    # Looks like a question — ends with ? or starts with a question word/phrase
    question_starters = (
        "what ", "how ", "why ", "when ", "who ", "where ",
        "is ", "are ", "was ", "were ", "will ", "would ",
        "can ", "could ", "should ", "do ", "does ", "did ",
        "tell me", "please tell", "please help", "help me",
        "i want to know", "can you tell",
        # Directed at the bot — insults, complaints, statements
        "you are", "you're", "you were", "you have", "you've",
        "you can", "you should", "you don't", "you cant",
        "i am ", "i'm ", "i was ", "i feel ",
    )
    if t.endswith("?") or t.startswith(question_starters):
        return False
    # Known commands / single-word inputs
    if t in ("hi", "hello", "hey", "help", "reminders", "unpaid", "earnings", "how", "cancel", "paid"):
        return False
    # Must have at least one digit (date/time/amount) or a time-of-day word
    if not re.search(r'\d|\btoday\b|\btomorrow\b|\bmorning\b|\bevening\b|\bnight\b|\bnext\b', t):
        return False
    return True


def _log_ai_call(phone: str, message: str):
    """Persist the message that triggered an AI call — for auditing and parser improvement."""
    try:
        from repositories.db_pool import get_connection, release_connection
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO ai_call_logs (user_id, message) VALUES (%s, %s)",
                (phone, message[:500])
            )
            conn.commit()
        finally:
            cur.close()
            release_connection(conn)
    except Exception as e:
        print(f"[AI log] Failed to save: {e}")


def _normalise_text(text: str) -> str:
    """
    Normalise common input variations before parsing:
      - "3.30pm" / "3.30 pm"  → "3:30pm"
      - "3.30"                 → "3:30"
      - "at 3" / "at 5"       → "at 3pm" / "at 5pm"  (business-hours PM inference)
    Leaves prices like "1200.50" untouched.
    """
    # Dot-as-colon: "3.30pm" → "3:30pm"
    text = re.sub(r'\b(\d{1,2})\.([0-5]\d)\s*(am|pm)\b', r'\1:\2\3', text, flags=re.I)
    text = re.sub(r'\b([01]?\d|2[0-3])\.([0-5]\d)\b(?!\d)', r'\1:\2', text)

    # Morning context: "morning at 11" → "morning at 11am" (hours 8–12 that PM inference misses)
    if re.search(r'\bmorning\b', text, re.I):
        def _infer_am(m):
            h = int(m.group(1))
            mins = m.group(2) or ""
            if 8 <= h <= 12:
                return f"at {h}{mins}am"
            return m.group(0)
        text = re.sub(r'\bat\s+([1-9]|1[0-2])(:\d{2})?\b(?!(?::\d{2})?\s*(?:am|pm))', _infer_am, text, flags=re.I)

    # "at X" PM inference: hours 1–7 without am/pm → almost always PM in business context
    # "at 8", "at 9" left alone — ambiguous (could be morning appointment)
    def _infer_pm(m):
        h = int(m.group(1))
        mins = m.group(2) or ""   # ":30" or ""
        if 1 <= h <= 7:
            return f"at {h}{mins}pm"
        return m.group(0)   # leave unchanged

    # Lookahead must also skip optional :MM so "at 6:07am" is not split into "at 6pm" + ":07am"
    text = re.sub(r'\bat\s+([1-9]|1[0-2])(:\d{2})?\b(?!(?::\d{2})?\s*(?:am|pm))', _infer_pm, text, flags=re.I)
    return text


def extract_reminder_details(message_text: str, phone: str = "unknown") -> dict:
    """
    Extraction priority:
      1. Normalise text (dot-time, PM inference)
      2. Local parser (free, instant)
      3. OpenAI — only when local missed date/time AND all guards pass
      4. Local result anyway if OpenAI also fails
    """
    normalised = _normalise_text(message_text)

    # Step 1: local parser
    result = _local_extract(normalised)

    if result.get("date") and result.get("time"):
        return result  # Both found — done, no AI needed

    # Step 2: decide whether to call AI
    has_time_hint = bool(re.search(
        r'\b\d{1,2}(?::\d{2})?\s*(?:am|pm)\b'
        r'|\bat\s+\d{1,2}\b'
        r'|\b(?:morning|afternoon|evening|night|noon|midnight|baje|subah|shaam|raat)\b'
        r'|\b\d{1,2}:\d{2}\b',
        normalised, re.I
    ))

    should_call_ai = (
        not result.get("date") or
        (result.get("date") and not result.get("time") and has_time_hint)
    )

    if should_call_ai:
        # Guard 1: message must look like an order (not a question/command/greeting)
        if not _looks_like_order(message_text):
            return result

        # Guard 2: rate limit — check plan from DB (default trial if unknown)
        try:
            from repositories.user_repository import get_user_plan
            plan = get_user_plan(phone) or "trial"
        except Exception:
            plan = "trial"

        if not _ai_allowed(phone, plan):
            print(f"[AI] Rate-limited: phone=***{phone[-4:]} plan={plan}")
            return result

        # Guard 3: truncate to 300 chars — caps token cost regardless of message length
        safe_text = message_text[:300]

        _ai_record_call(phone)
        _log_ai_call(phone, message_text)
        ai_result = _call_openai_once(safe_text, phone)
        if ai_result:
            if not result.get("date"):
                return ai_result
            if ai_result.get("time"):
                result["time"] = ai_result["time"]
                result["confidence"] = "high"
            return result

    return result


def _local_extract(text: str) -> dict:
    """Run the local parser chain. Never raises."""
    try:
        from parser.extractors.datetime_extractor import extract_datetime
        from parser.extractors.task_extractor import extract_task
        import re

        # Strip remind/notify phrases BEFORE date extraction so two dates don't confuse the parser
        text_for_dt = re.sub(r'\bremind\b.*', '', text, flags=re.I).strip()
        text_for_dt = re.sub(r'\bnotify\b.*', '', text_for_dt, flags=re.I).strip()
        # Normalise time formats (e.g. "3.30" → "3:30") before handing to datetime extractor
        text_for_dt = _normalise_text(text_for_dt)

        dt             = extract_datetime(text_for_dt)
        payment_fields = _extract_payment_fields(text)
        reminder_offset = _extract_reminder_offset(text)
        customer_notify_option = _extract_notify_option(text)

        # Strip phone numbers and payment keywords from text before task extraction
        clean_text = _strip_payment_tokens(text, payment_fields)
        task_cleaned = extract_task(clean_text.lower())

        # Preserve original casing: only use cleaned task if it's meaningful
        task = task_cleaned.strip() if (task_cleaned and len(task_cleaned.strip()) > 3) else clean_text.strip()

        date = dt.get("date")
        time = dt.get("time")

        if date and time:
            confidence = "high"
        elif date:
            confidence = "medium"
        else:
            confidence = "low"

        result = {"task": task, "date": date, "time": time, "confidence": confidence}
        result.update(payment_fields)
        if reminder_offset:
            result["reminder_offset"] = reminder_offset
        if customer_notify_option:
            result["customer_notify_option"] = customer_notify_option
        return result
    except Exception as e:
        print("Local extraction error:", e)
        return {"task": text.strip(), "date": None, "time": None, "confidence": "low"}


def _extract_reminder_offset(text: str):
    """
    Extract a custom reminder offset from phrases like:
      "remind day before", "remind 1 day before", "remind morning",
      "remind 9am", "remind at 10am", "remind 2 hrs before", "remind 1 hr before"

    Returns one of: "day_before", "morning", "2hr", "1hr", "HH:MM", or None.
    """
    import re

    t = text.lower()

    # Must contain the word "remind" to trigger offset parsing
    if "remind" not in t:
        return None

    # "day before" / "1 day before" / "tomorrow" style
    if re.search(r'remind\w*\s+(?:\d+\s+)?day\s+before', t):
        return "day_before"

    # "morning" (same day 8am)
    if re.search(r'remind\w*\s+(?:in\s+the\s+)?morning', t):
        return "morning"

    # "2 hrs/hours before"
    if re.search(r'remind\w*\s+2\s*hr(?:s|ours?)?\s+before', t):
        return "2hr"

    # "1 hr/hour before"
    if re.search(r'remind\w*\s+1\s*hr(?:s|ours?)?\s+before', t):
        return "1hr"

    # "remind on DATE at TIME" — specific date+time for reminder
    # e.g. "remind on 12th April at 4pm", "remind 12 Apr 9am"
    date_time_match = re.search(
        r'remind\w*\s+(?:on\s+)?(\d{1,2}(?:st|nd|rd|th)?\s+\w+|\w+\s+\d{1,2}(?:st|nd|rd|th)?)'
        r'(?:\s+at\s+|\s+)(\d{1,2})(?::(\d{2}))?\s*(am|pm)?',
        t, re.I
    )
    if date_time_match:
        try:
            from parser.extractors.datetime_extractor import extract_datetime
            remind_text = date_time_match.group(0).replace("remind", "").replace("on ", "").strip()
            dt = extract_datetime(remind_text)
            if dt.get("date") and dt.get("time"):
                return f"abs:{dt['date']} {dt['time']}"
        except Exception:
            pass

    # Specific time like "remind 9am", "remind at 10:30am", "remind 9:00"
    time_match = re.search(
        r'remind\w*\s+(?:at\s+)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)?',
        t
    )
    if time_match:
        hour   = int(time_match.group(1))
        minute = int(time_match.group(2) or 0)
        ampm   = time_match.group(3)
        if ampm == "pm" and hour != 12:
            hour += 12
        elif ampm == "am" and hour == 12:
            hour = 0
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return f"{hour:02d}:{minute:02d}"

    return None


def _extract_notify_option(text: str):
    """
    Extract inline customer notification timing from phrases like:
      "notify day before", "notify morning", "notify on due date", "notify no"
    Returns one of: "day_before", "morning", "on_due_date", "no", or None.
    """
    import re
    t = text.lower()
    if "notify" not in t:
        return None
    if re.search(r'\bnotify\s+(?:day\s+before|1\s+day\s+before)', t):
        return "day_before"
    if re.search(r'\bnotify\s+(?:in\s+the\s+)?morning', t):
        return "morning"
    if re.search(r'\bnotify\s+(?:on\s+)?(?:due\s+date|due\s+day|delivery|the\s+day)', t):
        return "on_due_date"
    if re.search(r'\bnotify\s+no\b', t):
        return "no"
    return None


def _strip_payment_tokens(text: str, payment_fields: dict) -> str:
    """Remove phone numbers, payment keywords, and remind/notify phrases from text so the task stays clean."""
    import re
    t = text

    # Strip common sentence-starter filler before the actual task content
    # e.g. "There is a booking for Anjali ..." → "Anjali ..."
    _FILLER_PREFIXES = [
        r'there\s+is\s+an?\s+(?:booking|order|reminder)\s+(?:for\s+)?',
        r'i\s+have\s+an?\s+(?:booking|order)\s+(?:for\s+)?',
        r'(?:please\s+)?(?:add|save|set|create|make)\s+an?\s+(?:booking|order|reminder)\s+(?:for\s+)?',
        r'(?:please\s+)?(?:add|save|set|create)\s+(?:a\s+)?reminder\s+(?:for\s+)?',
        r'booking\s+for\b\s*',
        r'order\s+for\b\s*',
    ]
    for pattern in _FILLER_PREFIXES:
        t = re.sub(r'^\s*' + pattern, '', t, flags=re.I).strip()

    # Remove matched phone number (10-digit Indian mobile, with optional +91/91 prefix)
    if payment_fields.get("customer_phone"):
        digits = payment_fields["customer_phone"][2:]   # strip leading "91"
        t = re.sub(r'(?:\+91|91)?' + re.escape(digits), '', t)

    # Remove "remind ..." / "set reminder ..." / "notify ..." phrases — everything to end of string
    t = re.sub(r'\b(?:and\s+)?(?:set\s+)?remind\w*\b.*', '', t, flags=re.I)
    t = re.sub(r'\bnotify\b.*', '', t, flags=re.I)

    # Remove payment keyword phrases: "total 1200", "advance 300", "paid 300", etc.
    t = re.sub(
        r'\b(?:total|advance|adv|paid|deposit|amount|charge|order|rupees?|rs\.?|₹)\s*[:\-]?\s*\d+(?:\.\d+)?\b',
        '', t, flags=re.I
    )
    # Remove bare numbers that were labelled amounts (e.g. "1200 advance")
    t = re.sub(
        r'\b\d+(?:\.\d+)?\s*(?:total|advance|adv|paid|deposit|rupees?|rs\.?)\b',
        '', t, flags=re.I
    )
    # Strip date/time words: "13th April", "April", "5pm", "at 5pm", "tomorrow", etc.
    t = re.sub(r'\b\d{1,2}(?:st|nd|rd|th)?\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*\b', '', t, flags=re.I)
    t = re.sub(r'\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*\s+\d{1,2}(?:st|nd|rd|th)?\b', '', t, flags=re.I)
    t = re.sub(r'\b(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\b', '', t, flags=re.I)
    t = re.sub(r'\b(?:at\s+)?\d{1,2}(?::\d{2})?\s*(?:am|pm)\b', '', t, flags=re.I)
    # Strip bare "at N" or "at N:MM" that have no am/pm (e.g. "at 11", "at 11:30")
    t = re.sub(r'\bat\s+\d{1,2}(?::\d{2})?\b', '', t, flags=re.I)
    t = re.sub(r'\b(?:day\s+after\s+tomorrow|tomorrow|today|tonight|morning|afternoon|evening|next\s+\w+|end\s+of\s+(?:the\s+)?(?:week|month))\b', '', t, flags=re.I)
    # Strip bare ordinals ONLY (13th, 1st, 2nd) — NOT bare numbers like "8" which are quantities
    t = re.sub(r'\b\d{1,2}(?:st|nd|rd|th)\b', '', t)

    # Strip trailing punctuation
    t = re.sub(r'[.,;!?]+$', '', t.strip())

    # Collapse extra whitespace and strip dangling prepositions/conjunctions at end
    t = re.sub(r'\s{2,}', ' ', t).strip()
    t = re.sub(r'\s+\b(?:at|on|by|for|of|to|and|the|a|an)\b\s*$', '', t, flags=re.I).strip()
    return t


def _extract_payment_fields(text: str) -> dict:
    """
    Extract customer_phone, total, advance from free-form text.
    Returns only the keys that were found.
    """
    import re
    result = {}

    # --- customer phone (Indian mobile: 10 digits starting 6-9, or +91 prefix) ---
    phone_match = re.search(r'(?<!\d)(?:\+91|91)?([6-9]\d{9})(?!\d)', text)
    if phone_match:
        digits = phone_match.group(1)
        result["customer_phone"] = "91" + digits

    # --- amounts: collect all money-like numbers ---
    # matches: ₹850, Rs 850, rs850, 850 rs, 850 rupees, standalone integers >= 10
    money_pattern = r'(?:₹|rs\.?\s*|rupees?\s*)(\d+(?:\.\d+)?)|(\d+(?:\.\d+)?)\s*(?:rs\.?|rupees?)'
    money_matches = [
        float(m.group(1) or m.group(2))
        for m in re.finditer(money_pattern, text, re.I)
    ]
    # Bare integers (3+ digits, no currency symbol) as fallback pool
    bare_ints = [float(m.group()) for m in re.finditer(r'\b(\d{3,})\b', text)]

    # --- Compound patterns (try these first, before individual keyword search) ---

    # "200 paid 800 baaki/pending/due" → advance=200, pending=800
    compound_paid_pending = re.search(
        r'(?:rs\.?\s*|₹)?(\d+(?:\.\d+)?)\s*(?:paid|advance|adv|deposit)'
        r'\s+(?:rs\.?\s*|₹)?(\d+(?:\.\d+)?)\s*(?:pending|due|balance|remaining|baaki|baki)',
        text, re.I
    )
    # "500 advance 1500 total" / "300 paid 1200 total" → advance=500, total=1500
    compound_adv_total = re.search(
        r'(?:rs\.?\s*|₹)?(\d+(?:\.\d+)?)\s*(?:advance|adv|paid|deposit)'
        r'\s+(?:rs\.?\s*|₹)?(\d+(?:\.\d+)?)\s*(?:total|tot)',
        text, re.I
    )

    # advance / paid keyword: "advance 300", "300 advance", "300 paid", "paid 300", "300 diya"
    advance_val = None
    pending_val = None

    # "N pending/baaki M paid/advance" → advance=M, pending=N  (reverse of compound_paid_pending)
    compound_pending_paid = re.search(
        r'(?:rs\.?\s*|₹)?(\d+(?:\.\d+)?)\s*(?:pending|due|balance|remaining|baaki|baki)'
        r'\s+(?:rs\.?\s*|₹)?(\d+(?:\.\d+)?)\s*(?:paid|advance|adv|deposit)',
        text, re.I
    )

    if compound_paid_pending:
        advance_val = float(compound_paid_pending.group(1))
        pending_val = float(compound_paid_pending.group(2))
    elif compound_pending_paid:
        pending_val = float(compound_pending_paid.group(1))
        advance_val = float(compound_pending_paid.group(2))
    elif compound_adv_total:
        advance_val = float(compound_adv_total.group(1))
        # total_val set below from compound_adv_total.group(2)
    else:
        # Keyword-first for advance: "advance 300", fallback to "300 advance"
        adv_pattern = r'(?:advance|adv|paid|deposit|diya(?:\s+hai)?)\s*[:\-]?\s*(?:rs\.?\s*|₹)?(\d+(?:\.\d+)?)'
        adv_match = re.search(adv_pattern, text, re.I)
        if not adv_match:
            adv_pattern2 = r'(?:rs\.?\s*|₹)?(\d+(?:\.\d+)?)\s*(?:advance|adv|paid|deposit|diya)'
            adv_match = re.search(adv_pattern2, text, re.I)
        if adv_match:
            advance_val = float(adv_match.group(1))

        # pending / due / balance keyword: "pending 800", "800 pending", "due 500", "baaki 400"
        pend_pattern = r'(?:pending|due|balance|remaining|baaki|baki)\s*[:\-]?\s*(?:rs\.?\s*|₹)?(\d+(?:\.\d+)?)'
        pend_match = re.search(pend_pattern, text, re.I)
        if not pend_match:
            pend_pattern2 = r'(?:rs\.?\s*|₹)?(\d+(?:\.\d+)?)\s*(?:pending|due|balance|remaining|baaki|baki)'
            pend_match = re.search(pend_pattern2, text, re.I)
        if pend_match:
            pending_val = float(pend_match.group(1))

    # total keyword: prefer "N total" (number before keyword) over "total N" to avoid
    # ambiguity in "1200 total 300 advance" (correct: 1200 is total, not 300)
    total_val = None
    if compound_adv_total:
        total_val = float(compound_adv_total.group(2))
    else:
        tot_pattern2 = r'(?:rs\.?\s*|₹)?(\d+(?:\.\d+)?)\s*(?:total|tot|ka\s+order)'
        tot_match = re.search(tot_pattern2, text, re.I)
        if not tot_match:
            tot_pattern = r'(?:total|tot|amount|order|charge)\s*[:\-]?\s*(?:rs\.?\s*|₹)?(\d+(?:\.\d+)?)'
            tot_match = re.search(tot_pattern, text, re.I)
        if tot_match:
            total_val = float(tot_match.group(1))

    # "paid X and pending Y" → total = X + Y, advance = X
    if total_val is None and advance_val is not None and pending_val is not None:
        total_val = advance_val + pending_val

    # if no labelled total but exactly two distinct money amounts found → larger = total, smaller = advance
    if total_val is None and advance_val is None and len(money_matches) == 2:
        total_val   = max(money_matches)
        advance_val = min(money_matches)
    elif total_val is None and len(money_matches) == 1 and advance_val is None:
        total_val = money_matches[0]
    # Bare integer fallback: "850" alone → total
    elif total_val is None and advance_val is None and not money_matches and len(bare_ints) == 1:
        total_val = bare_ints[0]
    # Two bare integers, no keywords → larger=total, smaller=advance
    elif total_val is None and advance_val is None and not money_matches and len(bare_ints) == 2:
        total_val   = max(bare_ints)
        advance_val = min(bare_ints)

    # "fully paid 1500" / "full payment 1500" → advance = total (everything paid)
    # Run after all fallbacks so total_val is already resolved
    if re.search(r'\bfully\s+paid\b|\bfull\s+payment\b|\bpura\s+paid\b|\bsab\s+paid\b', text, re.I):
        if total_val is not None and advance_val is None:
            advance_val = total_val
        elif advance_val is not None and total_val is None:
            total_val = advance_val

    if total_val is not None:
        result["total"] = total_val
    if advance_val is not None:
        result["advance"] = advance_val

    return result


def _call_openai_once(message_text: str, phone: str = "unknown"):
    """Call OpenAI exactly once. Returns parsed dict or None on any failure."""
    if not OPENAI_API_KEY:
        return None

    import uuid
    request_id = uuid.uuid4().hex[:8]
    phone_hint = phone[-4:] if len(phone) >= 4 else phone
    print(f"[OpenAI] id={request_id} phone=***{phone_hint} msg={message_text[:80]!r}")

    from datetime import date
    today = date.today().isoformat()

    prompt = f"""Extract order/reminder details from this WhatsApp message sent by a small business vendor.
The sender may write in English, Hindi, or Hinglish.

Today's date: {today}

Return ONLY valid JSON — no markdown, no explanation.

Fields:
- task: what the order or appointment is (cleaned of date/time/amount words)
- date: due date in YYYY-MM-DD format resolved from today (or null)
- time: due time in HH:MM 24hr format (or null)
- customer_phone: 10-digit Indian mobile number if present in message (or null)
- total: total order amount as a number (or null)
- advance: advance/deposit already paid as a number (or null)
- confidence: "high" if clearly understood, "low" if guessing
- reminder_offset: if the message contains a "remind ..." phrase, return one of:
    "day_before" (for "remind day before", "remind 1 day before"),
    "morning" (for "remind morning" — 8am same day),
    "2hr" (for "remind 2 hrs before"),
    "1hr" (for "remind 1 hr before"),
    or a time string like "09:00" for "remind 9am" / "remind at 10am".
    Return null if no remind phrase is present.
- customer_notify_option: if the message contains a "notify ..." phrase, return one of:
    "day_before", "morning", "on_due_date", "no". Return null if not present.

Message:
{message_text}"""

    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": "You are a strict JSON extractor. Return only valid JSON."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0,
        "max_tokens": 150
    }

    try:
        response = requests.post(OPENAI_URL, headers=headers, json=payload, timeout=8)
        if response.status_code != 200:
            print("OpenAI error:", response.status_code)
            return None
        content = response.json()["choices"][0]["message"]["content"].strip()
        content = content.replace("```json", "").replace("```", "").strip()
        parsed = json.loads(content)
        # Normalise phone to WhatsApp format
        raw_phone = str(parsed.get("customer_phone") or "")
        import re as _re
        digits = _re.sub(r'\D', '', raw_phone)
        if len(digits) == 10 and digits[0] in "6789":
            parsed["customer_phone"] = "91" + digits
        elif len(digits) == 12 and digits.startswith("91"):
            parsed["customer_phone"] = digits
        else:
            parsed["customer_phone"] = None
        return parsed
    except Exception as e:
        print("OpenAI call failed:", e)
        return None


def parse_template_reply(text: str):
    """
    Parse a structured template reply sent back by the vendor, e.g.:

        Task: Priya cake
        Date: 13 Apr 6pm
        Phone: 9876543210
        Total: 1200
        Advance: 500

    Returns a dict with any recognised fields, or None if the text
    doesn't look like a template reply (no "Date:" label found).
    """
    import re

    # Must contain "Date:" to be treated as a template fill
    if not re.search(r'\bdate\s*:', text, re.I):
        return None

    def _field(label: str):
        m = re.search(rf'{label}\s*:\s*(.+)', text, re.I | re.MULTILINE)
        if not m:
            return None
        val = m.group(1).strip()
        val = re.sub(r'\[.*?\]', '', val).strip()   # remove hint brackets
        if val.lower() in ('skip', 'na', 'nahi', 'no', '-', ''):
            return None
        return val

    result = {}

    task_val = _field('task')
    if task_val:
        result['task'] = task_val

    date_val = _field('date')
    if date_val:
        try:
            from parser.extractors.datetime_extractor import extract_datetime
            dt = extract_datetime(date_val)
            result['date'] = dt.get('date')
            result['time'] = dt.get('time')
        except Exception:
            pass

    phone_val = _field('customer phone') or _field('phone')
    if phone_val:
        digits = re.sub(r'\D', '', phone_val)
        if len(digits) == 10 and digits[0] in '6789':
            result['customer_phone'] = '91' + digits
        elif len(digits) == 12 and digits.startswith('91'):
            result['customer_phone'] = digits

    total_val = _field('total')
    if total_val:
        m = re.search(r'\d+(?:\.\d+)?', total_val)
        if m:
            result['total'] = float(m.group())

    adv_val = _field('advance')
    if adv_val:
        m = re.search(r'\d+(?:\.\d+)?', adv_val)
        if m:
            result['advance'] = float(m.group())

    return result if result else None


def detect_business_type(business_name: str) -> str:
    name_lower = business_name.lower()

    checks = {
        "salon":       ["salon", "spa", "beauty", "hair", "nails", "parlour", "parlor", "makeup"],
        "tiffin":      ["tiffin", "dabba", "meals", "food", "kitchen", "catering"],
        "photography": ["photo", "studio", "click", "films", "photography"],
        "tailor":      ["tailor", "boutique", "stitch", "fashion", "dress", "clothing"],
        "baker":       ["baker", "bakery", "cake", "bake", "sweets", "mithai", "pastry"],
    }

    for biz_type, keywords in checks.items():
        if any(w in name_lower for w in keywords):
            return biz_type

    return "generic"
