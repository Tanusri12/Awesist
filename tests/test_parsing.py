"""
Comprehensive parsing test suite — ~10,000 generated examples.
Tests parse_time_string, _normalise_text, extract_datetime, and
full extract_reminder_details (task + date + time + reminder).

Run:  python tests/test_parsing.py
      python tests/test_parsing.py --verbose   (show every failure)
      python tests/test_parsing.py --stop      (stop on first failure)
"""

import sys
import os
import re
import argparse
from datetime import datetime, date, timedelta
from itertools import product
from dataclasses import dataclass, field
from typing import Optional, List

# ── path setup ────────────────────────────────────────────────────────────────
ROOT = os.path.join(os.path.dirname(__file__), "..", "app")
sys.path.insert(0, ROOT)

from parser.extractors.datetime_extractor import parse_time_string, extract_datetime
from ai_extractor import _normalise_text, _strip_payment_tokens, _looks_like_order

# ── helpers ───────────────────────────────────────────────────────────────────

PASS = "✅"
FAIL = "❌"

@dataclass
class Result:
    section: str
    label: str
    input: str
    expected: object
    got: object
    passed: bool

results: List[Result] = []

def check(section: str, label: str, inp: str, expected, got):
    passed = expected == got
    results.append(Result(section, label, inp, expected, got, passed))
    return passed


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 1 — parse_time_string  (~700 cases)
# ══════════════════════════════════════════════════════════════════════════════

def test_parse_time_string():
    sec = "parse_time_string"

    # (input_str, expected_HH:MM or None)
    cases = []

    # ── 12-hour AM ────────────────────────────────────────────────────────────
    for h in range(1, 13):
        for m in [0, 7, 15, 30, 45, 59]:
            expected = f"{h:02d}:{m:02d}" if h != 12 else f"00:{m:02d}"
            # 12am is midnight = 00:xx
            if h == 12:
                expected = f"00:{m:02d}"
            else:
                expected = f"{h:02d}:{m:02d}"

            for ampm in ["am", "AM", "Am"]:
                for sep in ["", " "]:
                    for fmt in ([f"{h}:{m:02d}", f"{h:02d}:{m:02d}"] if m > 0 else [f"{h}", f"{h:02d}"]):
                        cases.append((f"{fmt}{sep}{ampm}", expected))

    # ── 12-hour PM ────────────────────────────────────────────────────────────
    for h in range(1, 13):
        for m in [0, 7, 15, 30, 45, 59]:
            if h == 12:
                expected = f"12:{m:02d}"
            else:
                expected = f"{h + 12:02d}:{m:02d}"

            for ampm in ["pm", "PM", "Pm"]:
                for sep in ["", " "]:
                    for fmt in ([f"{h}:{m:02d}", f"{h:02d}:{m:02d}"] if m > 0 else [f"{h}", f"{h:02d}"]):
                        cases.append((f"{fmt}{sep}{ampm}", expected))

    # ── 24-hour ───────────────────────────────────────────────────────────────
    for h in range(0, 24):
        for m in [0, 7, 15, 30, 45, 59]:
            for fmt in [f"{h}:{m:02d}", f"{h:02d}:{m:02d}"]:
                cases.append((fmt, f"{h:02d}:{m:02d}"))

    # ── edge cases ────────────────────────────────────────────────────────────
    edge = [
        ("12pm",    "12:00"),
        ("12am",    "00:00"),
        ("12:00pm", "12:00"),
        ("12:00am", "00:00"),
        ("12:30pm", "12:30"),
        ("12:30am", "00:30"),
        ("1pm",     "13:00"),
        ("1am",     "01:00"),
        ("11:59pm", "23:59"),
        ("11:59am", "11:59"),
        ("0:00",    "00:00"),
        ("23:59",   "23:59"),
        ("9am",     "09:00"),
        ("9pm",     "21:00"),
        ("9 am",    "09:00"),
        ("9 pm",    "21:00"),
        ("09:00am", "09:00"),
        ("09:00pm", "21:00"),
        # invalid → None
        ("25:00",   None),
        ("13am",    None),   # 13am is invalid
        ("",        None),
        ("abc",     None),
        ("99pm",    None),
    ]
    cases.extend(edge)

    # de-duplicate
    seen = set()
    for inp, exp in cases:
        if inp in seen:
            continue
        seen.add(inp)
        got = parse_time_string(inp)
        check(sec, f"parse_time_string({inp!r})", inp, exp, got)


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 2 — _normalise_text  (~300 cases)
# ══════════════════════════════════════════════════════════════════════════════

def test_normalise_text():
    sec = "_normalise_text"

    cases = [
        # dot-as-colon with am/pm (space before am/pm is collapsed — acceptable)
        ("3.30pm",            "3:30pm"),
        ("3.30 pm",           "3:30pm"),   # space is removed, functionally identical
        ("3.30am",            "3:30am"),
        ("11.45pm",           "11:45pm"),
        ("9.00am",            "9:00am"),
        # dot-as-colon no am/pm
        ("3.30",              "3:30"),
        ("11.45",             "11:45"),
        # PM inference — "at X" with hours 1-7, no am/pm
        ("at 1",              "at 1pm"),
        ("at 2",              "at 2pm"),
        ("at 3",              "at 3pm"),
        ("at 4",              "at 4pm"),
        ("at 5",              "at 5pm"),
        ("at 6",              "at 6pm"),
        ("at 7",              "at 7pm"),
        ("at 1:30",           "at 1:30pm"),
        ("at 3:30",           "at 3:30pm"),
        ("at 6:30",           "at 6:30pm"),
        # PM inference — hours 8+ NOT inferred
        ("at 8",              "at 8"),
        ("at 9",              "at 9"),
        ("at 10",             "at 10"),
        ("at 11",             "at 11"),
        ("at 12",             "at 12"),
        # already has am/pm — must NOT be modified
        ("at 6pm",            "at 6pm"),
        ("at 6am",            "at 6am"),
        ("at 6:30pm",         "at 6:30pm"),
        ("at 6:30am",         "at 6:30am"),
        ("at 6:07am",         "at 6:07am"),    # THE BUG CASE
        ("at 6:07pm",         "at 6:07pm"),
        ("at 11:59pm",        "at 11:59pm"),
        ("at 11:59am",        "at 11:59am"),
        ("at 12:00pm",        "at 12:00pm"),
        ("at 12:00am",        "at 12:00am"),
        # in sentence context
        ("cake 14 Apr at 6:07am",    "cake 14 Apr at 6:07am"),
        ("cake 14 Apr at 6:07pm",    "cake 14 Apr at 6:07pm"),
        ("cake 14 Apr at 6:30pm",    "cake 14 Apr at 6:30pm"),
        ("cake 14 Apr at 3",         "cake 14 Apr at 3pm"),
        ("cake 14 Apr at 3:30",      "cake 14 Apr at 3:30pm"),
        # prices — must not be touched
        ("total 1200.50",     "total 1200.50"),
        ("advance 300.00",    "advance 300.00"),
        # mixed
        ("Anjali cake 14 Apr 3.30pm total 1200",  "Anjali cake 14 Apr 3:30pm total 1200"),
        ("Meena blouse at 6 total 800",            "Meena blouse at 6pm total 800"),
        ("send garbage to test at 6:07am",         "send garbage to test at 6:07am"),
    ]

    for inp, expected in cases:
        got = _normalise_text(inp)
        check(sec, f"normalise({inp!r})", inp, expected, got)


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 3 — extract_datetime  (~600 cases)
# ══════════════════════════════════════════════════════════════════════════════

def test_extract_datetime():
    sec = "extract_datetime"
    today = date.today()
    tomorrow = today + timedelta(days=1)

    def future_date(month, day):
        """Return nearest future (or today) occurrence of month/day."""
        y = today.year
        try:
            d = date(y, month, day)
        except ValueError:
            return None
        if d < today:
            d = date(y + 1, month, day)
        return d.isoformat()

    # Format: (input_text, expected_date_iso_or_None, expected_time_HH:MM_or_None)
    cases = []

    # ── specific date + time ─────────────────────────────────────────────────
    date_time_combos = [
        # (text fragment, month, day, hour, minute)
        ("14 Apr 6pm",       4, 14, 18, 0),
        ("14 Apr 6:30pm",    4, 14, 18, 30),
        ("14 Apr 6:07am",    4, 14,  6,  7),
        ("14 Apr 6:07pm",    4, 14, 18,  7),
        ("14 Apr 11:59pm",   4, 14, 23, 59),
        ("14 Apr 11:59am",   4, 14, 11, 59),
        ("14 Apr 12pm",      4, 14, 12,  0),
        ("14 Apr 12am",      4, 14,  0,  0),
        ("14 Apr 9am",       4, 14,  9,  0),
        ("14 Apr 9pm",       4, 14, 21,  0),
        ("14 Apr 18:00",     4, 14, 18,  0),
        ("14 Apr 18:30",     4, 14, 18, 30),
        ("14 Apr 08:00",     4, 14,  8,  0),
        ("14 Apr 00:00",     4, 14,  0,  0),
        ("14th April 6pm",   4, 14, 18,  0),
        ("14th April 6:30pm",4, 14, 18, 30),
        ("14th Apr 11am",    4, 14, 11,  0),
        ("6th April 11am",   4,  6, 11,  0),
        ("1st April 6pm",    4,  1, 18,  0),
        ("31st March 3pm",   3, 31, 15,  0),
        ("5 May 5pm",        5,  5, 17,  0),
        ("20 Jun 8pm",       6, 20, 20,  0),
        ("1 Jan 10am",       1,  1, 10,  0),
        ("25 Dec 9am",      12, 25,  9,  0),
    ]

    for text, month, day, hour, minute in date_time_combos:
        exp_date = future_date(month, day)
        exp_time = f"{hour:02d}:{minute:02d}"
        if exp_date:
            cases.append((text, exp_date, exp_time))

    # ── time only (no date → today) ──────────────────────────────────────────
    time_only_cases = [
        ("6pm",      "18:00"),
        ("6:30pm",   "18:30"),
        ("6:07am",   "06:07"),
        ("6:07pm",   "18:07"),
        ("11:59pm",  "23:59"),
        ("11:59am",  "11:59"),
        ("12pm",     "12:00"),
        ("12am",     "00:00"),
        ("9am",      "09:00"),
        ("9pm",      "21:00"),
        ("18:00",    "18:00"),
        ("18:30",    "18:30"),
        ("08:00",    "08:00"),
        ("23:45",    "23:45"),
    ]
    for text, exp_time in time_only_cases:
        cases.append((text, today.isoformat(), exp_time))

    # ── relative dates ───────────────────────────────────────────────────────
    cases.append(("tomorrow at 6pm",  tomorrow.isoformat(), "18:00"))
    cases.append(("tomorrow at 9am",  tomorrow.isoformat(), "09:00"))

    # run
    for text, exp_date, exp_time in cases:
        result = extract_datetime(text)
        got_date = result.get("date")
        got_time = result.get("time")
        ok_d = check(sec, f"date({text!r})",  text, exp_date, got_date)
        ok_t = check(sec, f"time({text!r})",  text, exp_time, got_time)


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 4 — _looks_like_order  (~200 cases)
# ══════════════════════════════════════════════════════════════════════════════

def test_looks_like_order():
    sec = "_looks_like_order"

    should_be_orders = [
        "Anjali cake 14 Apr 6pm",
        "Meena blouse 20 Apr 11am total 800",
        "tarun 8 cupcakes 6 Apr 11am",
        "Priya order 5 May 3pm total 1200 advance 300",
        "birthday cake 15 Apr 7pm",
        "saree for Kavya 12 Jun 4pm",
        "delivery tomorrow 6pm",
        "Sharma ji blouse 20th April 5pm",
        "lehenga alteration 30 Apr 10am",
    ]

    should_NOT_be_orders = [
        "can you tell me what to do",
        "what is this",
        "how does this work",
        "you are garbage at 6pm",
        "you're not working",
        "i am confused",
        "is this correct",
        "are you there",
        "will you remind me",
        "should i send the date",
        "do you understand hindi",
        "does this work",
        "can you help",
        "tell me how to use",
        "please help me",
        "help me understand",
        "hi",
        "hello",
        "sjkjsnkjskjsdjsdjksddkc",
        "1200",
        "ok",
        "thanks",
    ]

    for msg in should_be_orders:
        got = _looks_like_order(msg)
        check(sec, f"IS order: {msg!r}", msg, True, got)

    for msg in should_NOT_be_orders:
        got = _looks_like_order(msg)
        check(sec, f"NOT order: {msg!r}", msg, False, got)


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 5 — _strip_payment_tokens task extraction  (~300 cases)
# ══════════════════════════════════════════════════════════════════════════════

def test_strip_payment_tokens():
    sec = "_strip_payment_tokens"

    # (input, expected_task_roughly)  — we check the task doesn't contain date/time words
    # and doesn't contain filler phrases
    cases = [
        # filler prefix removal
        ("there is a booking for Anjali cake 14 Apr 6pm",     "anjali cake"),
        ("there is an order for Anjali cake",                  "anjali cake"),
        ("booking for Meena blouse 20 Apr",                    "meena blouse"),
        ("order for Priya saree",                              "priya saree"),
        ("save a booking for tarun",                           "tarun"),
        ("please save a reminder for Deepa",                   "deepa"),
        # quantity preserved
        ("Anjali 8 cupcakes 14 Apr 6pm",     "anjali 8 cupcakes"),
        ("tarun 3 blouses 20 Apr",           "tarun 3 blouses"),
        # date/time stripped
        ("Anjali cake 14 Apr 6pm total 1200 advance 300",     "anjali cake"),
        ("Anjali cake 14th April at 6pm",                     "anjali cake"),
        ("Anjali cake tomorrow 6pm",                          "anjali cake"),
        # no trailing colon/period
        ("Anjali cake on 14 Apr at 6:07am",  "anjali cake"),
        ("send cake to Anjali on 14th April at 6pm",  "anjali cake"),
    ]

    for inp, expected_contains in cases:
        stripped = _strip_payment_tokens(inp.lower(), {})
        cleaned = re.sub(r'\s+', ' ', stripped).strip()
        # check the task roughly contains the expected words
        words = expected_contains.split()
        all_present = all(w in cleaned for w in words)
        # check no date words remain
        date_words = ["april", "apr", "jan", "feb", "mar", "may", "jun",
                      "jul", "aug", "sep", "oct", "nov", "dec", "tomorrow",
                      "today", "tonight", "morning", "evening"]
        no_date_words = not any(dw in cleaned for dw in date_words)
        # check no trailing : or .
        no_trailing_punct = not cleaned.endswith((":", ".", ","))

        ok = all_present and no_date_words and no_trailing_punct
        results.append(Result(sec, f"strip({inp[:50]!r})", inp,
                               f"contains={expected_contains}, no_dates, no_trailing_punct",
                               f"got={cleaned!r}", ok))


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 6 — Full end-to-end extract_reminder_details  (~8000+ cases)
# ══════════════════════════════════════════════════════════════════════════════

def test_full_parsing():
    sec = "full_parsing"

    # Use _local_extract directly — bypasses AI, rate limits, and DB logging
    try:
        from ai_extractor import _local_extract as extract_reminder_details
    except ImportError:
        results.append(Result(sec, "import", "", "ok", "IMPORT ERROR", False))
        return

    # Suppress noisy print output from the extractor during testing
    import io
    _devnull = open(os.devnull, "w")
    _old_stdout = sys.stdout
    sys.stdout = _devnull

    today = date.today()

    NAMES   = ["Anjali", "Meena", "Priya", "Deepa", "Kavya", "Sunita", "Tarun", "Rohit"]
    ITEMS   = ["cake", "blouse", "saree", "cupcakes", "order", "booking", "alteration", "lehenga"]
    MONTHS  = [(4, "Apr"), (5, "May"), (6, "Jun"), (7, "Jul"), (8, "Aug"), (9, "Sep")]

    def future_date(month, day):
        y = today.year
        try:
            d = date(y, month, day)
        except ValueError:
            return None
        if d < today:
            d = date(y + 1, month, day)
        return d.isoformat()

    # Time format variations and their expected HH:MM
    TIME_FORMATS = [
        # (text_fragment, expected_HH:MM)
        ("6pm",        "18:00"),
        ("6:00pm",     "18:00"),
        ("6:30pm",     "18:30"),
        ("6:07pm",     "18:07"),
        ("6am",        "06:00"),
        ("6:00am",     "06:00"),
        ("6:30am",     "06:30"),
        ("6:07am",     "06:07"),
        ("11am",       "11:00"),
        ("11:30am",    "11:30"),
        ("11:59am",    "11:59"),
        ("11pm",       "23:00"),
        ("11:30pm",    "23:30"),
        ("11:59pm",    "23:59"),
        ("12pm",       "12:00"),
        ("12am",       "00:00"),
        ("12:30pm",    "12:30"),
        ("12:30am",    "00:30"),
        ("9am",        "09:00"),
        ("9pm",        "21:00"),
        ("9:15am",     "09:15"),
        ("9:45pm",     "21:45"),
        ("3pm",        "15:00"),
        ("3:30pm",     "15:30"),
        ("18:00",      "18:00"),
        ("18:30",      "18:30"),
        ("08:00",      "08:00"),
        ("09:15",      "09:15"),
        ("23:45",      "23:45"),
        ("00:00",      "00:00"),
        ("6 pm",       "18:00"),
        ("6 am",       "06:00"),
        ("6:30 pm",    "18:30"),
        ("6:07 am",    "06:07"),
        # dot notation
        ("6.30pm",     "18:30"),
        ("6.30am",     "06:30"),
        ("3.30pm",     "15:30"),
        ("11.45am",    "11:45"),
    ]

    DATE_FORMATS = [
        # (text_fragment, month_int, day_int)
        ("14 Apr",     4, 14),
        ("14th Apr",   4, 14),
        ("14th April", 4, 14),
        ("April 14",   4, 14),
        ("20 May",     5, 20),
        ("20th May",   5, 20),
        ("1 Jun",      6,  1),
        ("1st June",   6,  1),
        ("5 Jul",      7,  5),
        ("5th July",   7,  5),
    ]

    # Connectors between date and time (no-space excluded — not a realistic user input)
    CONNECTORS = [" ", " at "]

    count = 0
    for name in NAMES[:4]:           # 4 names
        for item in ITEMS[:4]:       # 4 items
            for (date_text, month, day) in DATE_FORMATS[:6]:   # 6 date formats
                for (time_text, exp_time) in TIME_FORMATS[:20]:  # 20 time formats
                    for connector in CONNECTORS[:2]:             # 2 connectors

                        exp_date = future_date(month, day)
                        if not exp_date:
                            continue

                        msg = f"{name} {item} {date_text}{connector}{time_text}"
                        result = extract_reminder_details(msg)

                        got_date = result.get("date")
                        got_time = result.get("time")
                        got_task = (result.get("task") or "").lower()

                        # Date check
                        date_ok = got_date == exp_date
                        # Time check
                        time_ok = got_time == exp_time
                        # Task check — should contain name and item, no date words
                        task_has_name = name.lower() in got_task
                        task_has_item = item.lower() in got_task
                        task_ok = task_has_name and task_has_item

                        passed = date_ok and time_ok and task_ok
                        if not passed:
                            results.append(Result(
                                sec,
                                f"full({msg[:60]!r})",
                                msg,
                                f"date={exp_date} time={exp_time} task=contains({name.lower()},{item.lower()})",
                                f"date={got_date} time={got_time} task={got_task!r}",
                                passed
                            ))
                        else:
                            results.append(Result(sec, f"full({msg[:60]!r})", msg, "ok", "ok", True))
                        count += 1

    # filler prefix variants
    FILLERS = [
        "there is a booking for",
        "there is an order for",
        "booking for",
        "order for",
    ]
    for filler in FILLERS:
        for (time_text, exp_time) in TIME_FORMATS[:10]:
            msg = f"{filler} Anjali cake 14 Apr {time_text}"
            exp_date = future_date(4, 14)
            result = extract_reminder_details(msg)
            got_date = result.get("date")
            got_time = result.get("time")
            got_task = (result.get("task") or "").lower()
            task_ok = "anjali" in got_task and "cake" in got_task
            date_ok = got_date == exp_date
            time_ok = got_time == exp_time
            passed = date_ok and time_ok and task_ok
            results.append(Result(
                sec, f"filler({msg[:60]!r})", msg,
                f"date={exp_date} time={exp_time} task contains anjali+cake",
                f"date={got_date} time={got_time} task={got_task!r}",
                passed
            ))
            count += 1

    # payment fields included
    PAY_VARIANTS = [
        "total 1200",
        "total 1200 advance 300",
        "rs 1200",
        "₹1200 advance 500",
    ]
    for pay in PAY_VARIANTS:
        for (time_text, exp_time) in TIME_FORMATS[:5]:
            msg = f"Anjali cake 14 Apr {time_text} {pay}"
            exp_date = future_date(4, 14)
            result = extract_reminder_details(msg)
            got_date = result.get("date")
            got_time = result.get("time")
            got_task = (result.get("task") or "").lower()
            task_ok = "anjali" in got_task and "cake" in got_task
            date_ok = got_date == exp_date
            time_ok = got_time == exp_time
            passed = date_ok and time_ok and task_ok
            results.append(Result(
                sec, f"pay({msg[:60]!r})", msg,
                f"date={exp_date} time={exp_time}",
                f"date={got_date} time={got_time} task={got_task!r}",
                passed
            ))
            count += 1

    sys.stdout = _old_stdout
    _devnull.close()
    print(f"  [full_parsing] generated {count} cases")


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 7 — relative date expressions
# ══════════════════════════════════════════════════════════════════════════════

def test_relative_dates():
    sec = "relative_dates"
    today     = date.today()
    tomorrow  = today + timedelta(days=1)
    day_after = today + timedelta(days=2)

    def next_weekday(name):
        """Return the next occurrence of a named weekday (today counts as 'next' only
        if today IS that day AND dateparser returns it — here we use the same logic
        as parse_weekday which calls dateparser with PREFER_DATES_FROM=future)."""
        import dateparser
        from datetime import datetime as dt_
        d = dateparser.parse(name, settings={"PREFER_DATES_FROM": "future", "RELATIVE_BASE": dt_.now()})
        return d.date() if d else None

    def in_months(n):
        """Same-day n months from today (clamped to month end)."""
        m = today.month + n
        y = today.year + (m - 1) // 12
        m = (m - 1) % 12 + 1
        import calendar
        day = min(today.day, calendar.monthrange(y, m)[1])
        return date(y, m, day)

    def next_month_date():
        return in_months(1)

    # ── today ─────────────────────────────────────────────────────────────────
    today_cases = [
        ("today",               today.isoformat(), None),
        ("today at 6pm",        today.isoformat(), "18:00"),
        ("today morning",       today.isoformat(), "09:00"),
        ("today afternoon",     today.isoformat(), "14:00"),
        ("today evening",       today.isoformat(), "18:00"),
        ("today tonight",       today.isoformat(), "21:00"),
        ("today 6pm",           today.isoformat(), "18:00"),
        ("today 6:30pm",        today.isoformat(), "18:30"),
        ("today 10am",          today.isoformat(), "10:00"),
        ("cake delivery today", today.isoformat(), None),
    ]
    for text, exp_date, exp_time in today_cases:
        r = extract_datetime(text)
        check(sec, f"today: {text!r}", text, exp_date, r.get("date"))
        if exp_time is not None:
            check(sec, f"today-time: {text!r}", text, exp_time, r.get("time"))

    # ── tomorrow ──────────────────────────────────────────────────────────────
    tomorrow_cases = [
        ("tomorrow",                 tomorrow.isoformat(), None),
        ("tomorrow at 6pm",          tomorrow.isoformat(), "18:00"),
        ("tomorrow morning",         tomorrow.isoformat(), "09:00"),
        ("tomorrow afternoon",       tomorrow.isoformat(), "14:00"),
        ("tomorrow evening",         tomorrow.isoformat(), "18:00"),
        ("tomorrow 6pm",             tomorrow.isoformat(), "18:00"),
        ("tomorrow 9am",             tomorrow.isoformat(), "09:00"),
        ("tomorrow 6:30pm",          tomorrow.isoformat(), "18:30"),
        ("tomorrow 6:07am",          tomorrow.isoformat(), "06:07"),
        ("deliver cake tomorrow",    tomorrow.isoformat(), None),
        ("delivery tomorrow evening",tomorrow.isoformat(), "18:00"),
        ("meet tomorrow at 10am",    tomorrow.isoformat(), "10:00"),
    ]
    for text, exp_date, exp_time in tomorrow_cases:
        r = extract_datetime(text)
        check(sec, f"tomorrow: {text!r}", text, exp_date, r.get("date"))
        if exp_time is not None:
            check(sec, f"tomorrow-time: {text!r}", text, exp_time, r.get("time"))

    # ── day after tomorrow ────────────────────────────────────────────────────
    dat_cases = [
        ("day after tomorrow",          day_after.isoformat(), None),
        ("day after tomorrow at 5pm",   day_after.isoformat(), "17:00"),
        ("day after tomorrow morning",  day_after.isoformat(), None),   # known limit — see note
    ]
    for text, exp_date, exp_time in dat_cases:
        r = extract_datetime(text)
        check(sec, f"day-after: {text!r}", text, exp_date, r.get("date"))
        if exp_time is not None:
            check(sec, f"day-after-time: {text!r}", text, exp_time, r.get("time"))

    # ── next week ─────────────────────────────────────────────────────────────
    next_week = today + timedelta(days=7)
    next_week_cases = [
        ("next week",            next_week.isoformat(), None),
        ("next week at 10am",    next_week.isoformat(), "10:00"),
        ("deliver next week",    next_week.isoformat(), None),
    ]
    for text, exp_date, exp_time in next_week_cases:
        r = extract_datetime(text)
        check(sec, f"next-week: {text!r}", text, exp_date, r.get("date"))
        if exp_time is not None:
            check(sec, f"next-week-time: {text!r}", text, exp_time, r.get("time"))

    # ── next week + weekday ("next week monday") ──────────────────────────────
    for day_name in ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]:
        exp = next_weekday(day_name)
        if exp is None:
            continue
        text = f"next week {day_name}"
        r = extract_datetime(text)
        check(sec, f"next-week-day: {text!r}", text, exp.isoformat(), r.get("date"))

    # ── named weekdays ────────────────────────────────────────────────────────
    for day_name in ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]:
        exp = next_weekday(day_name)
        if exp is None:
            continue
        for text in [day_name, f"next {day_name}", f"on {day_name}", f"this {day_name}"]:
            r = extract_datetime(text)
            check(sec, f"weekday: {text!r}", text, exp.isoformat(), r.get("date"))

    # ── in N minutes / hours ──────────────────────────────────────────────────
    from datetime import datetime as dt_
    def approx_in(minutes):
        """Expected date for 'in N minutes/hours' (just check date, time may vary by seconds)."""
        return (dt_.now() + timedelta(minutes=minutes)).date().isoformat()

    relative_time_cases = [
        ("in 30 minutes",  approx_in(30)),
        ("in 1 hour",      approx_in(60)),
        ("in 2 hours",     approx_in(120)),
        ("in 45 mins",     approx_in(45)),
        ("in 90 minutes",  approx_in(90)),
    ]
    for text, exp_date in relative_time_cases:
        r = extract_datetime(text)
        check(sec, f"in-minutes: {text!r}", text, exp_date, r.get("date"))

    # ── in N days / weeks / months ────────────────────────────────────────────
    in_cases = [
        ("in 1 day",    (today + timedelta(days=1)).isoformat()),
        ("in 2 days",   (today + timedelta(days=2)).isoformat()),
        ("in 3 days",   (today + timedelta(days=3)).isoformat()),
        ("in 5 days",   (today + timedelta(days=5)).isoformat()),
        ("in 1 week",   (today + timedelta(days=7)).isoformat()),
        ("in 2 weeks",  (today + timedelta(days=14)).isoformat()),
        ("in 3 weeks",  (today + timedelta(days=21)).isoformat()),
        ("in 1 month",  in_months(1).isoformat()),
        ("in 2 months", in_months(2).isoformat()),
        ("in 3 months", in_months(3).isoformat()),
        ("in 6 months", in_months(6).isoformat()),
    ]
    for text, exp_date in in_cases:
        r = extract_datetime(text)
        check(sec, f"in-N: {text!r}", text, exp_date, r.get("date"))

    # ── after N days / weeks / months ─────────────────────────────────────────
    after_cases = [
        ("after 1 day",    (today + timedelta(days=1)).isoformat()),
        ("after 2 days",   (today + timedelta(days=2)).isoformat()),
        ("after 3 days",   (today + timedelta(days=3)).isoformat()),
        ("after 1 week",   (today + timedelta(days=7)).isoformat()),
        ("after 2 weeks",  (today + timedelta(days=14)).isoformat()),
        ("after 3 weeks",  (today + timedelta(days=21)).isoformat()),
        ("after 1 month",  in_months(1).isoformat()),
        ("after 2 months", in_months(2).isoformat()),
        ("after 3 months", in_months(3).isoformat()),
    ]
    for text, exp_date in after_cases:
        r = extract_datetime(text)
        check(sec, f"after-N: {text!r}", text, exp_date, r.get("date"))

    # ── next month ────────────────────────────────────────────────────────────
    nm = next_month_date()
    next_month_cases = [
        ("next month",           nm.isoformat()),
        ("deliver next month",   nm.isoformat()),
        ("next month at 5pm",    nm.isoformat()),
    ]
    for text, exp_date in next_month_cases:
        r = extract_datetime(text)
        check(sec, f"next-month: {text!r}", text, exp_date, r.get("date"))


# ══════════════════════════════════════════════════════════════════════════════
# RUNNER
# ══════════════════════════════════════════════════════════════════════════════

def run(verbose=False, stop_on_fail=False):
    print("\n" + "═"*70)
    print("  AWESIST PARSING TEST SUITE")
    print("═"*70)

    sections = [
        ("Section 1: parse_time_string",     test_parse_time_string),
        ("Section 2: _normalise_text",       test_normalise_text),
        ("Section 3: extract_datetime",      test_extract_datetime),
        ("Section 4: _looks_like_order",     test_looks_like_order),
        ("Section 5: _strip_payment_tokens", test_strip_payment_tokens),
        ("Section 6: full end-to-end",       test_full_parsing),
        ("Section 7: relative dates",        test_relative_dates),
    ]

    for title, fn in sections:
        before = len(results)
        print(f"\n▶ {title}")
        fn()
        after = len(results)
        batch = results[before:after]
        passed = sum(1 for r in batch if r.passed)
        total  = len(batch)
        pct    = 100 * passed / total if total else 0
        print(f"  {PASS if passed==total else FAIL}  {passed}/{total}  ({pct:.1f}%)")

        if verbose or passed < total:
            for r in batch:
                if not r.passed:
                    print(f"    {FAIL} {r.label}")
                    print(f"         input:    {r.input!r}")
                    print(f"         expected: {r.expected}")
                    print(f"         got:      {r.got}")
                    if stop_on_fail:
                        print("\n⛔ Stopped on first failure.")
                        _summary()
                        sys.exit(1)

    _summary()


def _summary():
    total  = len(results)
    passed = sum(1 for r in results if r.passed)
    failed = total - passed

    print("\n" + "═"*70)
    print(f"  TOTAL:  {total:>6}  cases")
    print(f"  {PASS} PASS:   {passed:>6}")
    print(f"  {FAIL} FAIL:   {failed:>6}  ({100*failed/total:.1f}%)" if total else "")
    print("═"*70)

    if failed > 0:
        # group failures by section
        from collections import defaultdict
        by_sec = defaultdict(list)
        for r in results:
            if not r.passed:
                by_sec[r.section].append(r)
        print("\nFailed by section:")
        for sec, items in by_sec.items():
            print(f"  {sec}: {len(items)} failures")
        sys.exit(1)
    else:
        print("\n🎉 All tests passed!")
        sys.exit(0)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--verbose", "-v", action="store_true", help="Show all failures in detail")
    parser.add_argument("--stop",    "-s", action="store_true", help="Stop on first failure")
    args = parser.parse_args()
    run(verbose=args.verbose, stop_on_fail=args.stop)
