from ai_extractor import detect_business_type
from conversation_memory import get_state, set_state, clear_state
from config import TRIAL_DAYS
from repositories.user_repository import get_or_create_user, update_user_profile
from whatsapp import send_whatsapp_message


def handle_onboarding(phone: str, text: str, user_cache: dict):
    state = get_state(phone)

    if not state:
        get_or_create_user(phone)
        set_state(phone, {"step": "awaiting_business_name"})
        send_whatsapp_message(
            phone,
            "Hi! 👋 I'm Awesist — I help you run your business from WhatsApp.\n\n"
            "What's your business name?",
            show_help=False
        )
        return

    if state.get("step") == "awaiting_business_name":
        business_name = text.strip()
        if len(business_name) < 2:
            send_whatsapp_message(
                phone,
                "Please send your business name — e.g. *Anita's Bakery* or *Deepa's Salon*",
                show_help=False
            )
            return
        business_type = detect_business_type(business_name)
        update_user_profile(phone, business_name, business_type)
        user_cache.pop(phone, None)
        clear_state(phone)
        short_example = _onboarding_short_example(business_type)
        send_whatsapp_message(
            phone,
            f"Done! You're all set, *{business_name}* 🎉\n\n"
            f"Your {TRIAL_DAYS}-day free trial starts now — no card needed.\n\n"
            f"Save your first order — just type:\n"
            f"_{short_example}_\n\n"
            f"I'll remind you automatically ⏰",
            show_help=False
        )


def _onboarding_short_example(business_type: str) -> str:
    """One short, minimal example — just name, task, date, time."""
    examples = {
        "baker":       "Anjali chocolate cake 13 Apr 5pm",
        "salon":       "Meena bridal appointment 20 Apr 11am",
        "tailor":      "Ravi suit delivery 25 Apr 6pm",
        "tiffin":      "Sharma tiffin order 1 May 9am",
        "photography": "Anjali pre-wedding shoot 15 Apr 9am",
    }
    return examples.get(business_type, "Ravi order 20 Apr 5pm")