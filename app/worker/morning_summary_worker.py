from datetime import datetime
from repositories.user_repository import get_summary_users, mark_summary_sent
from repositories.reminder_repository import get_today_reminders, get_user_reminders
from whatsapp import send_whatsapp_message


def log(msg: str):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [MORNING] {msg}")


def run_morning_summary():
    log("Running morning summary")
    users = get_summary_users()
    sent = skipped = 0

    for user in users:
        user_id       = user["id"]
        business_name = user.get("business_name") or "there"
        first_name    = business_name.split()[0]

        try:
            today     = get_today_reminders(user_id)
            all_r     = get_user_reminders(user_id)
            today_ids = {r["id"] for r in today}
            upcoming  = [r for r in all_r if r["id"] not in today_ids]

            if not today and not upcoming:
                mark_summary_sent(user_id)
                skipped += 1
                continue

            lines = [f"Good morning, *{first_name}*! ☀️"]

            if today:
                lines.append(
                    f"\nToday — {datetime.now().strftime('%d %b')} "
                    f"({len(today)} reminder{'s' if len(today) > 1 else ''}):\n"
                )
                for i, r in enumerate(today, 1):
                    dt = r["reminder_time"]
                    if isinstance(dt, str):
                        dt = datetime.fromisoformat(dt)
                    lines.append(f"{i}. {r['task']} ⏰ {dt.strftime('%I:%M %p')}")
            else:
                lines.append("\nNo reminders today — enjoy the break! ☕")

            if upcoming:
                lines.append("\n*Coming up:*")
                for r in upcoming[:3]:
                    dt = r["reminder_time"]
                    if isinstance(dt, str):
                        dt = datetime.fromisoformat(dt)
                    lines.append(f"• {r['task']} — {dt.strftime('%d %b %I:%M %p')}")

            lines.append("\nReply *reminders* to see all · *help* for commands")

            send_whatsapp_message(user_id, "\n".join(lines), show_help=False)
            mark_summary_sent(user_id)
            sent += 1

        except Exception as e:
            log(f"Error for {user_id}: {e}")

    log(f"Done — sent: {sent}, skipped: {skipped}")