import re

def extract_phone(text):

    match = re.search(r'\b\d{10}\b', text)

    if match:
        return match.group()

    return None