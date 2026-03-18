ORDER_WORDS = [
    "order",
    "send",
    "deliver",
    "buy"
]

def is_order(msg: str):
    for word in ORDER_WORDS:
        if word in msg:
            return True
    return False