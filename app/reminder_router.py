REMINDER_WORDS = ["remind", "reminder", "remember", "booking", "book"]

def is_reminder(msg: str):
    for word in REMINDER_WORDS:
        if word in msg:
            return True
    return False