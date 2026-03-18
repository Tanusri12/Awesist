import re

def extract_name(text):
    pattern = r"\b(?:to|for)\s+([A-Z][a-z]+(?:\s[A-Z][a-z]+)*)"
    match = re.search(pattern, text)

    if match:
        return match.group(1)

    return None

