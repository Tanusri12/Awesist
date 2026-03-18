from database import get_connection

def save_reminder(phone, message, remind_at):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO reminders (phone, message, remind_at) VALUES (?, ?, ?)",
        (phone, message, remind_at)
    )

    conn.commit()
    conn.close()