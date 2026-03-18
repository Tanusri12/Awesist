import re


def extract_task(text: str):

    text = text.lower()

    # remove reminder phrases
    text = re.sub(r"\bremind me to\b", "", text)
    text = re.sub(r"\bremind me\b", "", text)

    # remove time phrases
    time_patterns = [
        r"\btomorrow\b",
        r"\btoday\b",
        r"\btonight\b",
        r"\bmorning\b",
        r"\bafternoon\b",
        r"\bevening\b",
        r"\bnext\s+\w+\b",
        r"\bin\s+\d+\s+\w+\b",
        r"\bon\s+\d{1,2}(st|nd|rd|th)\b",
        r"\b\d{1,2}(st|nd|rd|th)\b",
        r"\b\d{1,2}(:\d{2})?\s*(am|pm)\b"
    ]

    for pattern in time_patterns:
        text = re.sub(pattern, "", text)

    # remove extra spaces
    text = re.sub(r"\s+", " ", text).strip()

    return text if text else None