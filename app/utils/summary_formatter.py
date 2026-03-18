def format_morning_summary(summary):

    message = "🌅 Good Morning!\n\n"

    if summary["today"]:
        message += "🗓 Today\n"

        for r in summary["today"]:

            time_str = r["reminder_time"].strftime("%I:%M %p")

            message += f"• {time_str} – {r['task']}\n"

    if summary["upcoming"]:

        message += "\n⏳ Upcoming\n"

        for r in summary["upcoming"][:3]:

            time_str = r["reminder_time"].strftime("%d %b %I:%M %p")

            message += f"• {time_str} – {r['task']}\n"

    message += "\n\nReply:\nreminders → view all"

    return message