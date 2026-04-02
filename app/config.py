import os
from dotenv import load_dotenv

load_dotenv()

VERIFY_TOKEN    = os.getenv("VERIFY_TOKEN")
WHATSAPP_TOKEN  = os.getenv("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
DATABASE_URL    = os.getenv("DATABASE_URL")
OPENAI_API_KEY  = os.getenv("OPENAI_API_KEY")
ADMIN_SECRET         = os.getenv("ADMIN_SECRET")
META_APP_SECRET      = os.getenv("META_APP_SECRET", "")   # Meta App Dashboard → Settings → App Secret

# ─── Beta allowlist ────────────────────────────────────────────────────────────
# Comma-separated phone numbers (with country code, no +) allowed during beta.
# Leave empty to allow everyone.
# Example: "919876543210,919591914432"
BETA_ALLOWLIST_RAW   = os.getenv("BETA_ALLOWLIST", "")
BETA_ALLOWLIST       = {p.strip() for p in BETA_ALLOWLIST_RAW.split(",") if p.strip()}

MORNING_SUMMARY_HOUR   = int(os.getenv("MORNING_SUMMARY_HOUR", "8"))
REMINDER_POLL_INTERVAL = int(os.getenv("REMINDER_POLL_INTERVAL", "30"))

# ─── Razorpay ─────────────────────────────────────────────────────────────────
# Get from: dashboard.razorpay.com → Settings → API Keys
RAZORPAY_KEY_ID         = os.getenv("RAZORPAY_KEY_ID", "")
RAZORPAY_KEY_SECRET     = os.getenv("RAZORPAY_KEY_SECRET", "")
# Get from: dashboard.razorpay.com → Settings → Webhooks → Secret
RAZORPAY_WEBHOOK_SECRET = os.getenv("RAZORPAY_WEBHOOK_SECRET", "")

# ─── Subscription settings ────────────────────────────────────────────────────
SUBSCRIPTION_PRICE_INR = int(os.getenv("SUBSCRIPTION_PRICE_INR", "299"))
TRIAL_DAYS             = int(os.getenv("TRIAL_DAYS", "30"))

