import re as _re


def _is_key_value_line(line: str) -> bool:
    """
    Return True only if this line looks like a genuine key: value or key - value pair.

    Rules:
      - The key (left of the separator) must be 1–30 chars and contain no digits
        (avoids matching dates like "12-5-2025" or times like "10:30").
      - The key must not be empty after stripping.
      - The value (right of the separator) must be non-empty after stripping.
      - The separator must appear at a word boundary — i.e. surrounded by
        whitespace or at start/end of the key/value, not mid-word.
    """
    # Try colon separator: "Name: Priya" or "name : priya"
    colon_match = _re.match(r'^([^:\n]{1,30}):\s*(.+)$', line.strip())
    if colon_match:
        key = colon_match.group(1).strip()
        # Key must not be all-digits or contain digits (avoids "10:30", "14:00")
        if key and not _re.search(r'\d', key):
            return True

    # Try dash separator: "Name - Priya" (dash surrounded by spaces = explicit separator)
    dash_match = _re.match(r'^([^-\n]{1,30})\s-\s(.+)$', line.strip())
    if dash_match:
        key = dash_match.group(1).strip()
        if key and not _re.search(r'\d', key):
            return True

    return False


def is_structured(text: str) -> bool:
    """
    A message is treated as structured if it contains at least 3 lines that each
    look like a genuine key–value pair (e.g. "Name: Priya", "Date: 5th April").
    Mid-word hyphens ("priya-shop"), timestamps ("10:30"), and date strings
    ("12-5-2025") are no longer counted.
    """
    lines = text.split("\n")
    count = sum(1 for line in lines if _is_key_value_line(line))
    return count >= 3


def parse_structured(text: str):

    result = {}

    lines = text.split("\n")

    for line in lines:

        if ":" in line:
            key, value = line.split(":", 1)

        elif "-" in line:
            key, value = line.split("-", 1)

        else:
            continue

        key = key.strip().lower()
        value = value.strip()

        # Skip empty keys (e.g. separator lines like "---")
        if not key:
            continue

        result[key] = value

    return result