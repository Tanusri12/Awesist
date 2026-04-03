from whatsapp import send_whatsapp_message
from conversation_memory import clear_state


def handle_command(phone: str, text: str, user: dict = None) -> bool:
    """Handle only stateless, always-valid commands that need no routing context."""
    msg = text.lower().strip()

    # Cancel active conversation state
    if msg == "cancel":
        clear_state(phone)
        send_whatsapp_message(phone, "👍 Cancelled.", show_help=False)
        return True

    # Everything else (help, reminders, delete, track, etc.) → route_intent
    return False