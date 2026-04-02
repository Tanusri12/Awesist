import hashlib
import hmac

from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from fastapi.responses import PlainTextResponse
from threading import Thread

from config import VERIFY_TOKEN, ADMIN_SECRET, META_APP_SECRET, BETA_ALLOWLIST
from incoming_msg_processor import process_message
from worker.reminder_worker import run_worker


def _verify_meta_signature(raw_body: bytes, signature_header: str) -> bool:
    """Verify that the request came from Meta using HMAC-SHA256."""
    if not META_APP_SECRET:
        # If no secret configured, skip verification (dev mode)
        return True
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(
        META_APP_SECRET.encode(), raw_body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature_header)


def _extract_sender_phone(data: dict) -> str | None:
    """Pull the sender's phone number from the WhatsApp payload."""
    try:
        entry   = data["entry"][0]
        changes = entry["changes"][0]
        msgs    = changes["value"].get("messages", [])
        if msgs:
            return msgs[0].get("from", "")
    except (KeyError, IndexError):
        pass
    return None

app = FastAPI()


@app.on_event("startup")
def startup():
    thread = Thread(target=run_worker, daemon=True)
    thread.start()
    print("Awesist started")


@app.get("/webhook")
async def verify_webhook(request: Request):
    hub_mode         = request.query_params.get("hub.mode")
    hub_verify_token = request.query_params.get("hub.verify_token")
    hub_challenge    = request.query_params.get("hub.challenge")
    if hub_mode == "subscribe" and hub_verify_token == VERIFY_TOKEN:
        return PlainTextResponse(content=hub_challenge, status_code=200)
    return PlainTextResponse("Verification failed", status_code=403)


@app.post("/webhook")
async def receive_message(request: Request, background_tasks: BackgroundTasks):
    raw_body  = await request.body()
    signature = request.headers.get("X-Hub-Signature-256", "")

    # ── 1. Verify this request actually came from Meta ─────────────────────────
    if not _verify_meta_signature(raw_body, signature):
        print(f"[SECURITY] Invalid webhook signature — rejected")
        raise HTTPException(status_code=403, detail="Invalid signature")

    import json
    try:
        data = json.loads(raw_body)
    except Exception:
        raise HTTPException(status_code=400, detail="Bad JSON")

    # ── 2. Beta allowlist — ignore messages from unknown numbers ───────────────
    if BETA_ALLOWLIST:
        sender = _extract_sender_phone(data)
        if sender and sender not in BETA_ALLOWLIST:
            print(f"[SECURITY] Blocked unknown sender: ***{sender[-4:]}")
            return {"status": "ignored"}

    background_tasks.add_task(process_message, data)
    return {"status": "received"}


@app.post("/razorpay-webhook")
async def razorpay_webhook(request: Request):
    """
    Razorpay calls this endpoint when a payment_link.paid event fires.
    We verify the HMAC-SHA256 signature before processing.

    Configure in Razorpay Dashboard → Settings → Webhooks:
      URL:    https://your-domain.com/razorpay-webhook
      Events: payment_link.paid
    """
    raw_body  = await request.body()
    signature = request.headers.get("X-Razorpay-Signature", "")

    from services.subscription_service import handle_razorpay_webhook
    try:
        result = handle_razorpay_webhook(raw_body, signature)
        return result
    except ValueError as e:
        # Bad signature — reject immediately so Razorpay knows to retry
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # Log but return 200 so Razorpay doesn't retry indefinitely
        print(f"RAZORPAY WEBHOOK ERROR: {e}")
        return {"ok": False, "error": str(e)}


@app.get("/health")
async def health():
    return {"status": "ok", "service": "Awesist"}


@app.post("/admin/activate/{phone}")
async def admin_activate(phone: str, request: Request):
    """
    Manually activate subscription for a phone number.
    Requires X-Admin-Secret header matching ADMIN_SECRET env var.

    Usage:
        curl -X POST https://your-domain.com/admin/activate/919876543210 \
             -H "X-Admin-Secret: your-secret"
    """
    secret = request.headers.get("X-Admin-Secret", "")
    if not ADMIN_SECRET or secret != ADMIN_SECRET:
        raise HTTPException(status_code=403, detail="Forbidden")

    from repositories.user_repository import activate_subscription, get_or_create_user
    from whatsapp import send_whatsapp_message
    from services.subscription_service import _subscription_confirmed_msg

    activate_subscription(phone, months=1)
    user = get_or_create_user(phone)
    name = user.get("business_name") or "there"
    send_whatsapp_message(phone, _subscription_confirmed_msg(name), show_help=False)
    return {"ok": True, "phone": phone, "name": name}
