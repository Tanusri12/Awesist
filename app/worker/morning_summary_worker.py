from datetime import datetime
from repositories.user_repository import get_summary_users, mark_summary_sent
from repositories.reminder_repository import get_today_reminders_with_payment, get_user_reminders
from whatsapp import send_whatsapp_message
from worker.nudge_worker import run_nudge_worker


def log(msg: str):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [MORNING] {msg}")


def _to_dt(val):
    if val is None:
        return None
    if isinstance(val, str):
        return datetime.fromisoformat(val)
    return val


def _fmt_time(dt) -> str:
    """6 PM or 6:30 PM — no leading zero."""
    if not dt:
        return "—"
    return dt.strftime("%-I %p") if dt.minute == 0 else dt.strftime("%-I:%M %p")


def _fmt_date(dt) -> str:
    """Mon 6 Apr"""
    if not dt:
        return "—"
    return dt.strftime("%a %-d %b")


def _pay_line(r: dict) -> str:
    total   = r.get("total")
    balance = r.get("balance")
    advance = r.get("advance")
    if not total or float(total) <= 0:
        return ""
    bal = float(balance or 0)
    adv = float(advance or 0)
    if bal <= 0:
        return "   ✅ Fully paid"
    if adv > 0:
        return f"   💰 Rs.{int(adv)} paid  ·  *Rs.{int(bal)} pending*"
    return f"   💰 *Rs.{int(float(total))} pending*"


def run_morning_summary():
    log("Running morning summary")
    users = get_summary_users()
    sent = skipped = 0

    for user in users:
        user_id    = user["id"]
        first_name = (user.get("business_name") or "there").split()[0]

        try:
            today     = get_today_reminders_with_payment(user_id)
            all_r     = get_user_reminders(user_id)
            today_ids = {r["id"] for r in today}
            upcoming  = [r for r in all_r if r["id"] not in today_ids]

            if not today and not upcoming:
                mark_summary_sent(user_id)
                skipped += 1
                continue

            now_str = datetime.now().strftime("%-d %b")
            lines   = [f"☀️ *Good morning, {first_name}!*\n"]

            # ── Today ──────────────────────────────────────────────────────
            if today:
                lines.append(f"*📅 Today — {now_str}  ({len(today)} order{'s' if len(today)>1 else ''})*")
                for i, r in enumerate(today, 1):
                    task   = r.get("task") or "—"
                    due_dt = _to_dt(r.get("due_at"))
                    rem_dt = _to_dt(r.get("reminder_time"))
                    pay    = _pay_line(r)

                    lines.append(f"\n{i}. *{task.capitalize()}*")
                    lines.append(f"   🗓 Due: {_fmt_time(due_dt)}  🔔 Remind: {_fmt_time(rem_dt)}")
                    if pay:
                        lines.append(pay)
            else:
                lines.append(f"*📅 Today — {now_str}*")
                lines.append("No orders today — enjoy the break! ☕")

            # ── Coming up ──────────────────────────────────────────────────
            if upcoming:
                lines.append(f"\n*📆 Coming up*")
                for r in upcoming[:4]:
                    task   = r.get("task") or "—"
                    due_dt = _to_dt(r.get("due_at"))
                    rem_dt = _to_dt(r.get("reminder_time"))
                    pay    = _pay_line(r)

                    lines.append(f"\n· *{task.capitalize()}*  —  {_fmt_date(due_dt)}")
                    lines.append(f"   🗓 Due: {_fmt_time(due_dt)}  🔔 Remind: {_fmt_time(rem_dt)}")
                    if pay:
                        lines.append(pay)

            # ── Total unpaid ───────────────────────────────────────────────
            total_unpaid = sum(
                float(r.get("balance") or 0)
                for r in all_r
                if r.get("balance") and float(r["balance"]) > 0
            )
            if total_unpaid > 0:
                lines.append(f"\n💰 *Rs.{int(total_unpaid)} pending* across all orders")

            # ── Nudge tip ──────────────────────────────────────────────────
            try:
                nudge_text = run_nudge_worker(user_only=user)
                if nudge_text:
                    tip = "\n".join(
                        l for l in nudge_text.splitlines()
                        if l.strip() and not l.strip().startswith("Hey ")
                    ).strip()
                    if tip:
                        lines.append(f"\n💡 {tip}")
            except Exception:
                pass

            # ── Footer ─────────────────────────────────────────────────────
            lines.append("\nreminders  ·  unpaid  ·  help")

            send_whatsapp_message(user_id, "\n".join(lines), show_help=False)
            mark_summary_sent(user_id)
            sent += 1

        except Exception as e:
            log(f"Error for {user_id}: {e}")

    log(f"Done — sent: {sent}, skipped: {skipped}")
