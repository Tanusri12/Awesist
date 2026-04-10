import requests
from config import WHATSAPP_TOKEN, PHONE_NUMBER_ID


def mark_message_read(message_id: str):
    """
    Mark a received message as read so the sender sees blue ticks immediately.
    This gives instant confirmation the bot received their message.

    Note: WhatsApp Cloud API does not support typing indicators ('...') via API.
    That feature is only available in the on-premise Business API.
    Blue ticks are the best signal we can give using the Cloud API.
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


def send_whatsapp_message(phone_number: str, message: str, show_help: bool = False) -> bool:

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


def send_whatsapp_message_tracked(phone_number: str, message: str) -> str | None:
    """Send a message and return the wamid (WhatsApp message ID), or None on failure."""
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
        print(f"WA(tracked) → {phone_number[:6]}*** | status: {response.status_code}")
        if response.status_code != 200:
            print("WA ERROR:", response.text)
            return None
        data = response.json()
        return data.get("messages", [{}])[0].get("id")
    except Exception as e:
        print(f"WA EXCEPTION: {e}")
        return None