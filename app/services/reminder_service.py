from datetime import datetime
from repositories.reminder_repository import create_reminder


def schedule_reminder(user_id: str, task: str, reminder_dt: datetime) -> bool:
    """
    Save a reminder. Returns False if it's a duplicate or in the past.
    """

    if reminder_dt <= datetime.now():
        return False

    result = create_reminder(
        user_id=user_id,
        task=task,
        reminder_time=reminder_dt
    )

    return bool(result)
