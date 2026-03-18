import re
import dateparser

from datetime import datetime, timedelta
from dateparser.search import search_dates


# --------------------------------------------------
# SETTINGS
# --------------------------------------------------

SETTINGS = {
    "PREFER_DATES_FROM": "future",
    "RELATIVE_BASE": datetime.now()
}


# --------------------------------------------------
# Utility: detect time in text
# --------------------------------------------------

def detect_time(text):

    time_pattern = r"\b\d{1,2}(:\d{2})?\s*(am|pm)\b|\b\d{1,2}:\d{2}\b"
    match = re.search(time_pattern, text)

    return match.group(0) if match else None


# --------------------------------------------------
# Handle "day after tomorrow"
# --------------------------------------------------

def parse_day_after_tomorrow(text):

    if "day after tomorrow" not in text:
        return None

    dt = datetime.now() + timedelta(days=2)

    return {
        "date": dt.date().isoformat(),
        "time": None
    }


# --------------------------------------------------
# Handle "tomorrow"
# --------------------------------------------------

def parse_tomorrow(text):

    if "tomorrow" not in text:
        return None

    dt = datetime.now() + timedelta(days=1)

    return {
        "date": dt.date().isoformat(),
        "time": None
    }


# --------------------------------------------------
# Handle evening / morning / tonight
# --------------------------------------------------

def parse_day_periods(text):

    now = datetime.now()

    periods = {
        "morning": "09:00",
        "afternoon": "14:00",
        "evening": "18:00",
        "tonight": "21:00"
    }

    for word, default_time in periods.items():

        if f"tomorrow {word}" in text:

            dt = now + timedelta(days=1)

            return {
                "date": dt.date().isoformat(),
                "time": default_time
            }

        if word in text:

            return {
                "date": now.date().isoformat(),
                "time": default_time
            }

    return None


# --------------------------------------------------
# Handle "next week"
# --------------------------------------------------

def parse_next_week(text):

    if "next week" not in text:
        return None

    dt = datetime.now() + timedelta(days=7)

    return {
        "date": dt.date().isoformat(),
        "time": None
    }


# --------------------------------------------------
# Handle day-of-month like "13th April" or "31st"
# --------------------------------------------------

# Month name → number lookup (full + 3-letter abbreviation)
_MONTH_NAMES = {
    "january": 1,  "jan": 1,
    "february": 2, "feb": 2,
    "march": 3,    "mar": 3,
    "april": 4,    "apr": 4,
    "may": 5,
    "june": 6,     "jun": 6,
    "july": 7,     "jul": 7,
    "august": 8,   "aug": 8,
    "september": 9,"sep": 9,  "sept": 9,
    "october": 10, "oct": 10,
    "november": 11,"nov": 11,
    "december": 12,"dec": 12,
}


def _extract_month_from_text(text: str):
    """Return (month_int, year_int) if a month name is found in text, else (None, None)."""
    text_lower = text.lower()
    for name, num in _MONTH_NAMES.items():
        if re.search(r'\b' + name + r'\b', text_lower):
            return num, None   # year is resolved later
    return None, None


def parse_day_of_month(text):

    match = re.search(r'\b(\d{1,2})(st|nd|rd|th)\b', text)

    if not match:
        return None

    day = int(match.group(1))
    now = datetime.now()

    # Check if a specific month name is mentioned ("13th April", "5th March 2026")
    explicit_month, _ = _extract_month_from_text(text)

    if explicit_month:
        # Use explicit month; pick nearest future year
        year = now.year
        try:
            dt = datetime(year, explicit_month, day)
        except ValueError:
            return None   # e.g. 31st April is invalid
        # If that date has already passed, bump to next year
        if dt < now:
            try:
                dt = datetime(year + 1, explicit_month, day)
            except ValueError:
                return None
    else:
        # No month given — use current month, bump if already past
        try:
            dt = datetime(now.year, now.month, day)
        except ValueError:
            return None

        if dt < now:
            month = now.month + 1
            year  = now.year
            if month > 12:
                month = 1
                year += 1
            try:
                dt = datetime(year, month, day)
            except ValueError:
                return None

    return {
        "date": dt.date().isoformat(),
        "time": None
    }


# --------------------------------------------------
# Handle relative time (in 2 hours)
# --------------------------------------------------

def parse_relative_time(text):

    pattern = r"in\s*\d+\s*(min|mins|minute|minutes|hour|hours)"

    match = re.search(pattern, text)

    if not match:
        return None

    phrase = match.group(0)

    dt = dateparser.parse(phrase, settings=SETTINGS)

    if not dt:
        return None

    return {
        "date": dt.date().isoformat(),
        "time": dt.strftime("%H:%M")
    }


# --------------------------------------------------
# Handle weekdays
# --------------------------------------------------

def parse_weekday(text):

    weekdays = [
        "monday", "tuesday", "wednesday",
        "thursday", "friday", "saturday", "sunday"
    ]

    for day in weekdays:

        if day in text:

            dt = dateparser.parse(day, settings=SETTINGS)

            if dt:

                time = detect_time(text)

                return {
                    "date": dt.date().isoformat(),
                    "time": dt.strftime("%H:%M") if time else None
                }

    return None


# --------------------------------------------------
# Handle explicit times
# --------------------------------------------------

def parse_time_only(text):

    time = detect_time(text)

    if not time:
        return None

    dt = dateparser.parse(time, settings=SETTINGS)

    if not dt:
        return None

    return {
        "date": dt.date().isoformat(),
        "time": dt.strftime("%H:%M")
    }


# --------------------------------------------------
# Fallback natural language
# --------------------------------------------------

def parse_natural_language(text):

    results = search_dates(text, settings=SETTINGS)

    if not results:
        return None

    phrase, dt = results[0]

    time = detect_time(text)

    return {
        "date": dt.date().isoformat(),
        "time": dt.strftime("%H:%M") if time else None
    }


# --------------------------------------------------
# Main extractor
# --------------------------------------------------

def extract_datetime(text):

    text = text.lower().strip()

    parsers = [
        parse_day_after_tomorrow,
        parse_tomorrow,
        parse_day_periods,
        parse_next_week,
        parse_day_of_month,
        parse_relative_time,
        parse_weekday,
        parse_time_only,
        parse_natural_language
    ]

    result = None
    for parser in parsers:
        result = parser(text)
        if result:
            break

    if not result:
        return {"date": None, "time": None}

    # Second pass: if we found a date but no time, try to extract time separately.
    # This handles cases like "13th April at 5pm" where parse_day_of_month
    # returns the date but drops the time before parse_time_only can run.
    if result.get("date") and not result.get("time"):
        time_str = detect_time(text)
        if time_str:
            dt = dateparser.parse(time_str, settings=SETTINGS)
            if dt:
                result["time"] = dt.strftime("%H:%M")

    return result