import os
from dotenv import load_dotenv

load_dotenv()

VERIFY_TOKEN    = os.getenv("VERIFY_TOKEN")
WHATSAPP_TOKEN  = os.getenv("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
DATABASE_URL    = os.getenv("DATABASE_URL")
OPENAI_API_KEY  = os.getenv("OPENAI_API_KEY")
ADMIN_SECRET    = os.getenv("ADMIN_SECRET")

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

