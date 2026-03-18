from repositories.reminder_repository import get_user_reminders
from datetime import datetime


def generate_user_summary(user_id):

    reminders = get_user_reminders(user_id)

    today = []
    upcoming = []

    now = datetime.now()

    for r in reminders:

        reminder_time = r["reminder_time"]

        if reminder_time.date() == now.date():
            today.append(r)

        elif reminder_time > now:
            upcoming.append(r)

    return {
        "today": today,
        "upcoming": upcoming
    }