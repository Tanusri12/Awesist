import json
import requests
from config import OPENAI_API_KEY

OPENAI_URL = "https://api.openai.com/v1/chat/completions"


def extract_reminder_details(message_text: str, phone: str = "unknown") -> dict:
    """
    Extraction priority:
      1. Local parser (free, instant) — used if it finds a date
      2. OpenAI API (called at most once) — only if local found no date
      3. Local result anyway (confidence=low) — if OpenAI also fails/errors
    """
    # Step 1: local parser
    result = _local_extract(message_text)
    if result.get("date"):
        return result

    # Step 2: OpenAI once — only when local found nothing
    ai_result = _call_openai_once(message_text, phone)
    if ai_result:
        return ai_result

    # Step 3: return whatever local got (task only, date=None, time=None)
    return result


def _local_extract(text: str) -> dict:
    """Run the local parser chain. Never raises."""
    try:
        from parser.extractors.datetime_extractor import extract_datetime
        from parser.extractors.task_extractor import extract_task

        dt             = extract_datetime(text)
        payment_fields = _extract_payment_fields(text)
        reminder_offset = _extract_reminder_offset(text)

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


def _strip_payment_tokens(text: str, payment_fields: dict) -> str:
    """Remove phone numbers, payment keywords, and remind phrases from text so the task stays clean."""
    import re
    t = text

    # Remove matched phone number (10-digit Indian mobile, with optional +91/91 prefix)
    if payment_fields.get("customer_phone"):
        digits = payment_fields["customer_phone"][2:]   # strip leading "91"
        t = re.sub(r'(?:\+91|91)?' + re.escape(digits), '', t)

    # Remove "remind ..." phrase — everything from "remind" to end of string
    # Handles: "remind day before", "remind on 12th April at 4pm", "remind 1 hr before", etc.
    t = re.sub(r'\bremind\b.*', '', t, flags=re.I)

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
    # Collapse extra whitespace
    t = re.sub(r'\s{2,}', ' ', t).strip()
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

    # advance keyword: "advance 300", "300 advance", "300 paid", "paid 300", "300 diya"
    advance_val = None
    adv_pattern = r'(?:advance|adv|paid|deposit|diya(?:\s+hai)?)\s*[:\-]?\s*(?:rs\.?\s*|₹)?(\d+(?:\.\d+)?)'
    adv_match = re.search(adv_pattern, text, re.I)
    if not adv_match:
        adv_pattern2 = r'(?:rs\.?\s*|₹)?(\d+(?:\.\d+)?)\s*(?:advance|adv|paid|deposit|diya)'
        adv_match = re.search(adv_pattern2, text, re.I)
    if adv_match:
        advance_val = float(adv_match.group(1))

    # total keyword: "total 850", "850 total", "1200 ka", "order 1200"
    total_val = None
    tot_pattern = r'(?:total|tot|amount|order|charge)\s*[:\-]?\s*(?:rs\.?\s*|₹)?(\d+(?:\.\d+)?)'
    tot_match = re.search(tot_pattern, text, re.I)
    if not tot_match:
        tot_pattern2 = r'(?:rs\.?\s*|₹)?(\d+(?:\.\d+)?)\s*(?:total|tot|ka\s+order)'
        tot_match = re.search(tot_pattern2, text, re.I)
    if tot_match:
        total_val = float(tot_match.group(1))

    # if no labelled total but exactly two distinct money amounts found → larger = total, smaller = advance
    if total_val is None and advance_val is None and len(money_matches) == 2:
        total_val   = max(money_matches)
        advance_val = min(money_matches)
    elif total_val is None and len(money_matches) == 1 and advance_val is None:
        total_val = money_matches[0]

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

    phone_val = _field('phone')
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
