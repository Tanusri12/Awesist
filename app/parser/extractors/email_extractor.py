import re

def extract_email(text):

    match = re.search(r'\S+@\S+\.\S+', text)

    if match:
        return match.group()

    return None