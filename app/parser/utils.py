import re

def normalize_text(text: str) -> str:
    text = text.replace("\r", "")
    text = re.sub(r'[ \t]+', ' ', text)
    return text.strip()