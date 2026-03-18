# Awesist — WhatsApp Reminder Assistant

Never forget an order or appointment. Built on WhatsApp — no app to install.

---

## What was fixed in this version

| # | Bug | Fix |
|---|-----|-----|
| 1 | `start_scheduler()` called but never imported in `main.py` | Added import |
| 2 | OpenAI API key hardcoded in `ai_extractor.py` | Moved to `.env`, switched to Claude Haiku |
| 3 | Reminder worker used `r["phone"]` but DB returned `user_id` | Added `phone` field explicitly in fetch query |
| 4 | `conversation_memory` used in-memory dict — wiped on restart | Replaced with PostgreSQL `conversation_memory` table |
| 5 | `morning_summary_worker` imported from `workers.` (wrong path) | Fixed to `worker.` |
| 6 | `is_valid_message` blocked "hi" — new users got silence | New users bypass `is_valid_message` and go to onboarding |
| 7 | No onboarding flow — first-time users got no response | Added full onboarding: Hi → business name → ready |
| 8 | No business name stored — messages impersonal | Added `business_name` + `business_type` columns to users |
| 9 | AI extractor never called in actual message flow | Integrated into `handle_create_reminder` |
| 10 | Morning summary sent empty messages | Now skips users with no reminders |

---

## Stack

| Layer | Technology | Cost |
|-------|-----------|------|
| API server | FastAPI + Uvicorn | Free |
| Hosting | Railway / Render free tier | Free |
| Database | Supabase or Neon (PostgreSQL) | Free |
| WhatsApp | Meta Cloud API | Free (first 1000 conversations/month) |
| AI parsing | Claude Haiku | ~Rs. 2/baker/month |

---

## Setup

### 1. Clone and install

```bash
cd app
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Fill in your values
```

### 3. Run database migrations

Run these SQL files in order against your PostgreSQL database:

```
db/migration/V1__init_schema.sql
db/migration/V2__add_indexes.sql
db/migration/V3__reminder_retry_support.sql
db/migration/V4__conversation_memory.sql
db/migration/V5__onboarding_and_memory.sql   ← new
```

Using Supabase? Paste each file into the SQL editor and run.

### 4. Start the server

```bash
cd app
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### 5. Expose with ngrok (local testing)

```bash
ngrok http 8000
```

Copy the `https://xxxx.ngrok.io` URL.

### 6. Configure WhatsApp webhook

In Meta Developer Console:
- Webhook URL: `https://your-domain/webhook`
- Verify token: same as `VERIFY_TOKEN` in your `.env`
- Subscribe to: `messages`

---

## How it works

```
Baker sends "Hi"
    → Bot asks for business name
    → Baker replies "Anita's Bakery"
    → Bot detects type (baker) and saves profile
    → Baker is onboarded ✅

Baker sends "Remind me to call Priya about her cake order at 6 PM"
    → Claude Haiku extracts: task + date + time
    → Saved to PostgreSQL reminders table
    → At 6 PM: worker fires, sends WhatsApp reminder ✅

Every morning at 8 AM:
    → Scheduler fires morning summary
    → Each user gets today's reminders + upcoming ones ✅
```

---

## Project structure

```
app/
├── main.py                      # FastAPI entry point
├── config.py                    # All env vars (no hardcoded secrets)
├── whatsapp.py                  # Send WhatsApp messages
├── ai_extractor.py              # Claude Haiku — parse reminders + detect biz type
├── incoming_msg_processor.py    # Main message router + onboarding
├── conversation_memory.py       # Persistent state (PostgreSQL)
│
├── commands/
│   └── commands.py              # help, reminders, delete N, cancel
│
├── parser/
│   ├── parser.py                # Intent classifier
│   └── extractors/              # date, time, name extractors
│
├── repositories/
│   ├── db_pool.py               # Connection pool
│   ├── user_repository.py       # Users + business profile
│   └── reminder_repository.py  # CRUD + due reminder fetch
│
├── services/
│   └── reminder_service.py      # Schedule reminder (validates + saves)
│
├── scheduler/
│   └── scheduler.py             # APScheduler — 8 AM morning summary
│
└── worker/
    ├── reminder_worker.py       # Polls every 30s, fires due reminders
    └── morning_summary_worker.py # Sends daily briefing

db/migration/
├── V1__init_schema.sql
├── V2__add_indexes.sql
├── V3__reminder_retry_support.sql
├── V4__conversation_memory.sql
└── V5__onboarding_and_memory.sql   ← new
```
