IGNORE = [
    "hi",
    "hello",
    "ok",
    "okay",
    "thanks",
    "thank you",
    "test"
]

def should_ignore(msg: str):
    return msg in IGNORE or len(msg) < 3