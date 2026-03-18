"""
Subscription Service — Razorpay Payment Link integration.

Flow:
  1. User's trial expires  →  send_payment_link() is called.
  2. Razorpay sends a webhook POST /razorpay-webhook when the user pays.
  3. handle_razorpay_webhook() verifies the HMAC signature, finds the user
     by phone stored in the link's notes, and calls activate_subscription().

Razorpay docs:
  https://razorpay.com/docs/payments/payment-links/apis/
  https://razorpay.com/docs/webhooks/
"""

import hashlib
import hmac
import logging

import requests

from config import (
    RAZORPAY_KEY_ID,
    RAZORPAY_KEY_SECRET,
    RAZORPAY_WEBHOOK_SECRET,
    SUBSCRIPTION_PRICE_INR,
)
from repositories.user_repository import (
    activate_subscription,
    get_last_payment_link_id,
    save_payment_link_id,
)

logger = logging.getLogger(__name__)

RAZORPAY_API = "https://api.razorpay.com/v1"


# ─────────────────────────────────────────────────────────────────────────────
# Create / reuse a Payment Link
# ─────────────────────────────────────────────────────────────────────────────

def get_or_create_payment_link(phone: str, business_name: str) -> str:
    """
    Returns a Razorpay short_url for the ₹99 subscription.

    If we already created a link for this user (stored in last_payment_link_id),
    we fetch it first.  If it's still unpaid we reuse the same URL so the user
    always sees one clean link and we don't litter Razorpay with duplicates.
    """
    existing_id = get_last_payment_link_id(phone)
    if existing_id:
        try:
            resp = requests.get(
                f"{RAZORPAY_API}/payment_links/{existing_id}",
                auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET),
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                # Reuse the link only if it's still pending payment
                if data.get("status") in ("created", "partially_paid"):
                    return data["short_url"]
        except Exception as e:
            logger.warning("Could not fetch existing payment link %s: %s", existing_id, e)

    # Create a fresh payment link
    return _create_payment_link(phone, business_name)


def _create_payment_link(phone: str, business_name: str) -> str:
    payload = {
        "amount":       SUBSCRIPTION_PRICE_INR * 100,   # Razorpay expects paise
        "currency":     "INR",
        "description":  "Awesist — Monthly Subscription (₹99)",
        "customer": {
            "contact": f"+{phone}",
            "name":    business_name or "Awesist User",
        },
        # Don't let Razorpay spam the user — we send the link ourselves via WhatsApp
        "notify":           {"whatsapp": False, "sms": False, "email": False},
        "reminder_enable":  False,
        # Store phone in notes so we can identify the user in the webhook
        "notes":            {"phone": phone},
    }

    try:
        resp = requests.post(
            f"{RAZORPAY_API}/payment_links",
            auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET),
            json=payload,
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        link_id  = data["id"]
        short_url = data["short_url"]
        save_payment_link_id(phone, link_id)
        logger.info("Created Razorpay payment link %s for %s", link_id, phone[:6])
        return short_url
    except Exception as e:
        logger.error("Razorpay payment link creation failed for %s: %s", phone[:6], e)
        raise


# ─────────────────────────────────────────────────────────────────────────────
# Webhook handler
# ─────────────────────────────────────────────────────────────────────────────

def verify_webhook_signature(raw_body: bytes, signature: str) -> bool:
    """
    Razorpay signs the raw request body with HMAC-SHA256 using your
    webhook secret.  Returns True only if the signatures match.
    """
    if not RAZORPAY_WEBHOOK_SECRET:
        logger.warning("RAZORPAY_WEBHOOK_SECRET not set — skipping signature check")
        return True   # Allow in dev/test when secret is not configured

    expected = hmac.new(
        RAZORPAY_WEBHOOK_SECRET.encode(),
        raw_body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


def handle_razorpay_webhook(raw_body: bytes, signature: str) -> dict:
    """
    Called from the FastAPI route POST /razorpay-webhook.

    Supported events:
      - payment_link.paid  →  activate subscription for the user

    Returns {"ok": True} on success, raises ValueError on bad signature.
    """
    if not verify_webhook_signature(raw_body, signature):
        raise ValueError("Invalid Razorpay webhook signature")

    import json
    payload = json.loads(raw_body)
    event   = payload.get("event")
    logger.info("Razorpay webhook received: %s", event)

    if event == "payment_link.paid":
        _handle_payment_link_paid(payload)

    return {"ok": True}


def _subscription_confirmed_msg(name: str) -> str:
    return (
        f"✅ Payment received! Welcome aboard, *{name}*. 🎉\n\n"
        "Your Awesist subscription is active for the next *30 days*.\n\n"
        "*Here's what you can do right now:*\n"
        "📝 *Add an order* — just type it naturally\n"
        "   _Priya cake 15th April 5pm_\n\n"
        "📋 *reminders* — see all upcoming orders\n"
        "💰 *unpaid* — check pending balances\n"
        "📈 *earnings* — see this month's collections\n\n"
        "💡 Type *how* anytime to see message examples."
    )


def _handle_payment_link_paid(payload: dict):
    """
    Extract the phone from payment link notes and activate subscription.
    """
    try:
        entity = payload["payload"]["payment_link"]["entity"]
        phone  = entity.get("notes", {}).get("phone")
        if not phone:
            logger.error("payment_link.paid webhook missing phone in notes: %s", entity)
            return

        activate_subscription(phone, months=1)
        logger.info("Subscription activated for %s***", phone[:6])

        # Clear the stored link id so a fresh one is created at next renewal
        save_payment_link_id(phone, None)

        # Send a confirmation WhatsApp message
        try:
            from whatsapp import send_whatsapp_message
            from repositories.user_repository import get_or_create_user
            user = get_or_create_user(phone)
            name = user.get("business_name") or "there"
            send_whatsapp_message(
                phone,
                _subscription_confirmed_msg(name),
                show_help=False,
            )
        except Exception as e:
            logger.warning("Could not send payment confirmation WhatsApp: %s", e)

    except (KeyError, TypeError) as e:
        logger.error("Malformed payment_link.paid payload: %s", e)
