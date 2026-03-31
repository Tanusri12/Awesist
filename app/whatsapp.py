import requests
from config import WHATSAPP_TOKEN, PHONE_NUMBER_ID


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