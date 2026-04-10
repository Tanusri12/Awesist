import re
from parser.utils import normalize_text
from parser.structured_parser import is_structured, parse_structured

from parser.extractors.phone_extractor import extract_phone
from parser.extractors.email_extractor import extract_email
from parser.extractors.quantity_extractor import extract_quantity
from parser.extractors.datetime_extractor import extract_datetime
from parser.extractors.name_extractor import extract_name
from parser.extractors.task_extractor import extract_task
from dateparser.search import search_dates


def detect_command(text):

    text = text.lower().strip()

    if text in ["help", "menu", "commands"]:
        return "HELP"

    if text in ["reminders", "bookings", "list", "show reminders", "show bookings"]:
        return "LIST_REMINDERS"

    if text.startswith("delete"):
        return "DELETE_REMINDER"

    if text == "invite":
        return "INVITE"

    return None


def parse_message(message: str):

    text = normalize_text(message)

    # 1️⃣ structured messages
    if is_structured(text):
        return parse_structured(text)

    # 2️⃣ unstructured extraction
    result = {}

    result["name"] = extract_name(text)
    result["phone"] = extract_phone(text)
    result["email"] = extract_email(text)
    result["quantity"] = extract_quantity(text)

    dt = extract_datetime(text)

    result["date"] = dt["date"]
    result["time"] = dt["time"]

    result["task"] = extract_task(text)
    print("DATETIME:", dt)

    return result



def classify_intent(text: str):

    text_lower = text.lower().strip()

    # -----------------------------
    # LIST REMINDERS
    # -----------------------------
    if text_lower in [
        "reminders", "bookings",
        "my reminders", "my bookings",
        "list reminders", "list bookings",
        "show reminders", "show bookings",
        "list"
    ]:
        return "list_reminders"

    # -----------------------------
    # DELETE REMINDER
    # -----------------------------
    if re.search(r"\b(delete|remove|cancel)\s+\d+\b", text_lower):
        return "delete_reminder"

    # -----------------------------
    # EXPLICIT REMINDER WORDS
    # -----------------------------
    reminder_words = ["remind", "reminder", "notify", "alert"]

    for word in reminder_words:
        if word in text_lower:
            return "create_reminder"

    # -----------------------------
    # DATE DETECTION
    # -----------------------------
    dates = search_dates(
        text,
        settings={"PREFER_DATES_FROM": "future"}
    )

    if dates:
        return "create_reminder"

    # -----------------------------
    # TIME DETECTION
    # -----------------------------
    if re.search(r"\b\d{1,2}\s?(am|pm)\b", text_lower):
        return "create_reminder"

    # -----------------------------
    # RELATIVE TIME
    # -----------------------------
    if re.search(r"\bin\s+\d+\s+(minute|minutes|hour|hours|day|days)\b", text_lower):
        return "create_reminder"

    # -----------------------------
    # FALLBACK (ASSUME TASK)
    # -----------------------------
    words = text_lower.split()
    if len(words) >= 4:
        return "create_reminder"

    return "unknown"





def is_valid_message(text: str) -> bool:

    if not text:
        return False

    text = text.strip().lower()

    greetings = [
        "hi",
        "hello",
        "hey",
        "good morning",
        "good evening"
    ]

    ignored_words = [
        "ok",
        "okay",
        "thanks",
        "thank you",
        "got it"
    ]

    if text in greetings or text in ignored_words:
        return False

    if len(text) < 3:
        return False

    if re.match(r'^[^\w\s]+$', text):
        return False

    return True
