	from apscheduler.schedulers.background import BackgroundScheduler
from whatsapp import send_whatsapp_message

scheduler = BackgroundScheduler()
scheduler.start()

def schedule_reminder(phone, message, remind_time):
	job_id = f"{phone}-{remind_time}"
    scheduler.add_job(
        send_reminder,
        trigger="date",
        run_date=remind_time,
        args=[phone, message],
        id=job_id,
        replace_existing=True
    )

def send_reminder(phone, message):
    print("REMINDER TRIGGERED")
    send_whatsapp_message(phone, f"⏰ Reminder:\n{message}")