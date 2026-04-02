import requests
import time
from config import WHATSAPP_TOKEN, PHONE_NUMBER_ID


def mark_message_read(message_id: str):
    """
    Mark a received message as read so the sender sees blue ticks immediately.
    This gives instant confirmation the bot received their message.
    """
    try:
        url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
        requests.post(
            url,
            headers={
                "Authorization": f"Bearer {WHATSAPP_TOKEN}",
                "Content-Type": "application/json",
            },
            json={
                "messaging_product": "whatsapp",
                "status": "read",
                "message_id": message_id,
            },
            timeout=5,
        )
    except Exception as e:
        print(f"MARK READ ERROR: {e}")


def send_typing_indicator(phone: str):
    """
    Show the '...' typing bubble to the user while the bot is processing.
    Called immediately after mark_message_read so the user sees:
      1. Blue ticks  (message received)
      2. '...'       (bot is thinking)
      3. Reply       (bot responds)

    Uses WhatsApp Cloud API typing action — fails silently if unsupported.
    """
    try:
        url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
        requests.post(
            url,
            headers={
                "Authorization": f"Bearer {WHATSAPP_TOKEN}",
                "Content-Type": "application/json",
            },
            json={
                "messaging_product": "whatsapp",
                "to": phone,
                "type": "action",
                "action": "typing_on",
            },
            timeout=3,
        )
        # Give WhatsApp a moment to show the indicator before the reply arrives
        time.sleep(1)
    except Exception as e:
        print(f"TYPING INDICATOR ERROR: {e}")


def send_whatsapp_message(phone_number: str, message: str, show_help: bool = True) -> bool:
    if show_help:
        message = f"{message}\n\n_Reply *how* for examples  ·  *help* for all commands_"

    url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"

    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }

    payload = {
        "messaging_product": "whatsapp",
        "to": phone_number,
        "type": "text",
        "text": {"body": message},
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        print(f"WA → {phone_number[:6]}*** | status: {response.status_code}")
        if response.status_code != 200:
            print("WA ERROR:", response.text)
            return False
        return True
    except requests.exceptions.Timeout:
        print(f"WA TIMEOUT → {phone_number[:6]}***")
        return False
    except Exception as e:
        print(f"WA EXCEPTION: {e}")
        return False