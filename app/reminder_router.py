REMINDER_WORDS = ["remind", "reminder", "remember"]

def is_reminder(msg: str):
    for word in REMINDER_WORDS:
        if word in msg:
            return True
    return False