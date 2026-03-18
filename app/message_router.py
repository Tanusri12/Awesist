from filters import should_ignore
from reminder_router import is_reminder
from order_router import is_order

def route_message(msg):

    if should_ignore(msg):
        return "ignore"

    if is_reminder(msg):
        return "reminder"

    if is_order(msg):
        return "order"

    return "ai"