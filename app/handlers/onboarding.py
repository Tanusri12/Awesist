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
        send_whatsapp_message(
            phone,
            f"Done! You're all set, *{business_name}*. 🎉\n\n"
            f"Your {TRIAL_DAYS}-day free trial starts now — no card needed.\n\n"
            "Just send me your orders and appointments in plain language — "
            "I'll track them, remind you, and even message your customer.\n\n"
            "Reply *how* to see examples  ·  *help* for all commands",
            show_help=False
        )
        # Second message: teach the one-message format with business-specific examples
        example = _onboarding_example(business_type)
        send_whatsapp_message(
            phone,
            f"💡 *The more you tell me, the less I ask*\n\n"
            f"Include any of these in your message:\n\n"
            f"📝 What the order is\n"
            f"📅 Date and time\n"
            f"📱 Customer's WhatsApp number _(I'll notify them too)_\n"
            f"💰 Total amount + advance paid\n\n"
            f"Example:\n_{example}_",
            show_help=False
        )


def _onboarding_example(business_type: str) -> str:
    examples = {
        "baker":       "Send chocolate cake to Priya on 13th April at 5pm. "
                       "Her number is 9876543210. Total Rs 1200, she paid Rs 300 advance.",
        "salon":       "Meena's bridal appointment on 20th April at 11am. "
                       "Her number 9876543210. Charge Rs 2500, advance Rs 500 received.",
        "tailor":      "Ravi suit delivery 25th April at 6pm. "
                       "His number 9876543210. Total Rs 3500, advance Rs 1000 paid.",
        "tiffin":      "Sharma ji monthly tiffin starts 1st May. "
                       "His number 9876543210. Total Rs 1800, advance Rs 900 diya.",
        "photography": "Priya pre-wedding shoot 15th April at 9am. "
                       "Her number 9876543210. Total Rs 8000, advance Rs 3000 received.",
    }
    return examples.get(
        business_type,
        "Send report to Ravi on 20th April at 5pm. "
        "His number 9876543210. Total Rs 5000, advance Rs 2000 paid."
    )