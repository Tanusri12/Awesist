import re

def extract_quantity(text):

    match = re.search(r'\d+\s?(kg|g|boxes?|pcs|pieces?|cakes?)', text, re.I)

    if match:
        return match.group()

    return None