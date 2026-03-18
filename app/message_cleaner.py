import re

def clean_message(text: str):
    text = text.lower().strip()

    text = re.sub(r"[^\w\s]", "", text)

    return text