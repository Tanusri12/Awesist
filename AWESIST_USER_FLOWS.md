# Awesist — Complete User Flow Document
**WhatsApp Bot | Version 1.0 | March 2026**

---

## Table of Contents
1. [Onboarding Flow](#1-onboarding-flow)
2. [Reminder Creation — Fast Path](#2-reminder-creation--fast-path)
3. [Reminder Creation — Slow Path](#3-reminder-creation--slow-path)
4. [Edit Reminder Flow](#4-edit-reminder-flow)
5. [List & Delete Reminders](#5-list--delete-reminders)
6. [Payment Tracking Flow](#6-payment-tracking-flow)
7. [Earnings / Income Flow](#7-earnings--income-flow)
8. [Subscription & Trial Flow](#8-subscription--trial-flow)
9. [Automated Background Flows](#9-automated-background-flows)
10. [Help, Examples & Error Handling](#10-help-examples--error-handling)
11. [WhatsApp Message Templates](#11-whatsapp-message-templates)

---

## 1. Onboarding Flow

**Triggered when:** A new phone number sends its first message.

### Flow

```
User:  Hi
Bot:   Hi! I'm Awesist — I make sure you never forget an order or appointment. 👋
       What's your business name?

User:  Anita's Bakery
Bot:   Done! You're all set, Anita's Bakery. 🎉
       Your 30-day free trial starts now — no card needed.
       [Sends business-specific onboarding example]
```

### Onboarding Examples by Business Type

| Business Type | Example Message Shown to User |
|---|---|
| Baker | Send chocolate cake to Priya on 13th April at 5pm. Her number is 9876543210. Total Rs 1200, she paid Rs 300 advance. |
| Salon | Meena's bridal appointment on 20th April at 11am. Her number 9876543210. Charge Rs 2500, advance Rs 500 received. |
| Tailor | Ravi suit delivery 25th April at 6pm. His number 9876543210. Total Rs 3500, advance Rs 1000 paid. |
| Tiffin | Sharma ji monthly tiffin starts 1st May. His number 9876543210. Total Rs 1800, advance Rs 900 diya. |
| Photography | Priya pre-wedding shoot 15th April at 9am. Her number 9876543210. Total Rs 8000, advance Rs 3000 received. |
| Default | Send report to Ravi on 20th April at 5pm. His number 9876543210. Total Rs 5000, advance Rs 2000 paid. |

### Validation Rules
- Business name must be at least 2 characters
- If invalid: *"Please send your business name — e.g. Anita's Bakery or Deepa's Salon"*
- Business type is auto-detected by AI from the name
- Trial starts immediately — no card required

---

## 2. Reminder Creation — Fast Path

**Triggered when:** User sends a message containing both a task AND a date/time in one message.

### Scenario A — Full Details in One Message

```
User:  Send chocolate cake to Priya on 13th April at 5pm.
       Her number is 9876543210. Total Rs 1200, she paid Rs 300 advance.

Bot:   ✅ All saved!

       📝 Chocolate cake for Priya
       📅 Due: 13 Apr 2026 5:00 PM
       ⏰ Reminder: 13 Apr 3:00 PM (2 hrs before)
       💰 Rs.300 advance · Rs.900 balance pending
       📱 Customer will be notified on the due date.

       Reply unpaid to see pending balances · edit to update this
```

### Scenario B — Date/Time Only (No Payment)

```
User:  Priya cake 13th April 5pm

Bot:   ✅ Saved!

       📝 Priya cake
       📅 Due: 13 Apr 2026 5:00 PM
       ⏰ Reminder: 13 Apr 3:00 PM (2 hrs before)

       Reply unpaid to track payments · reminders to see all · edit to update this
```

### Scenario C — With Phone, No Payment (Bot Asks)

```
User:  Priya cake 13th April 5pm 9876543210

Bot:   ✅ Reminder set!

       📝 Priya cake
       📅 Due: 13 Apr 2026 5:00 PM
       ⏰ Reminder: 13 Apr 3:00 PM

       💰 What's the total order amount?
       Reply with amount e.g. 850 · or skip

User:  1200

Bot:   Total: Rs.1200

       💵 Advance received?
       Reply with amount e.g. 300 · no advance · full (fully paid)

User:  300

Bot:   ✅ All saved!

       📝 Priya cake
       📅 Due: 13 Apr 2026 5:00 PM
       ⏰ Reminder: 13 Apr 3:00 PM
       💰 Rs.300 advance · Rs.900 balance pending

       Reply unpaid anytime to see pending balances.
```

### Reminder Time Calculation Rules

| Condition | Reminder Set To |
|---|---|
| 2+ hours before due time available | Due time minus 2 hours |
| Less than 2 hours but 1+ min available | Due time minus 1 minute |
| Due time already in the past | 30 seconds from now |
| Reminder would equal due time | 1 minute before due |

### Validation Rules
- Due date must be at least 30 minutes in the future
- Phone numbers must be 10-digit Indian numbers starting with 6, 7, 8, or 9
- Phone stored as 91XXXXXXXXXX (with country code)
- Advance cannot exceed total amount

---

## 3. Reminder Creation — Slow Path

**Triggered when:** User sends a task but missing date/time.

### Flow — Bot Shows Template to Fill

```
User:  Priya cake

Bot:   📋 Fill in the date and send back:

       Task: Priya cake
       Date: [e.g. 13 Apr 6pm]
       Phone: [optional]
       Total: [optional]
       Advance: [optional]

User:  Task: Priya cake
       Date: 13 Apr 5pm
       Phone: 9876543210
       Total: 1200
       Advance: 300

Bot:   ✅ All saved! [same as fast path confirmation]
```

### Flow — Bot Asks for Time Separately

```
User:  Priya cake tomorrow

Bot:   ⏰ When should I remind you?
       Reply: 2 hrs before · day before · or a specific time like 1pm

User:  2 hrs before

Bot:   📱 Customer's WhatsApp number?
       I'll send them a reminder too.
       e.g. 9876543210 · or skip to not notify them

User:  skip

Bot:   💰 What's the total order amount?
       Reply with amount e.g. 850 · or skip

User:  skip

Bot:   ✅ Saved!

       📝 Priya cake
       📅 Due: 14 Apr 2026 12:00 PM
       ⏰ Reminder: 14 Apr 10:00 AM
```

### Generic Reminder Trigger (Meta Commands)

If user sends generic phrases like *"set a reminder"*, *"create reminder"*, *"add order"*:

```
Bot:   💡 Just tell me the order details directly — no need for commands!

       Examples:
         Priya cake 13th April 5pm
         Meena blouse stitching 20th April at 11am total 800

       Type how to see more examples.
```

### Accepted Time Formats
- `2 hrs before` / `day before` / `morning`
- `1pm` / `9am` / `6:30pm`
- `9am on 12 Apr`
- `tomorrow morning`
- `today evening`

---

## 4. Edit Reminder Flow

**Triggered when:** User replies `edit` immediately after saving a reminder.

```
Bot:   ✅ All saved!
       📝 Priya cake
       📅 Due: 13 Apr 5:00 PM
       ...
       Reply edit to update this

User:  edit

Bot:   ✏️ Update reminder

       Send the corrected details — just like you normally would:
         Priya cake 15th April 6pm
         Meena appointment 20th April at 11am total 2500 advance 500

User:  Priya cake 15th April 6pm total 1200 advance 500

Bot:   ✅ All saved!

       📝 Priya cake
       📅 Due: 15 Apr 2026 6:00 PM
       ⏰ Reminder: 15 Apr 4:00 PM
       💰 Rs.500 advance · Rs.700 balance pending
```

> **Note:** Edit updates the existing reminder in the database. It is only available immediately after saving (state: `just_saved`). Payment details are also updated if amounts are provided.

---

## 5. List & Delete Reminders

### List All Reminders

```
User:  reminders   (also: my reminders / list / show reminders)

Bot:   📋 Your reminders:

       1. Priya cake
          ⏰ Remind: 13 Apr 2026 3:00 PM
          📅 Due: 13 Apr 2026 5:00 PM

       2. Meena appointment
          ⏰ Remind: 20 Apr 2026 9:00 AM
          📅 Due: 20 Apr 2026 11:00 AM

       Reply: delete <number> · unpaid to see balances
```

### Delete a Reminder

```
User:  delete 1

Bot:   🗑️ Reminder deleted.
```

### Cancel Current Action

```
User:  cancel

Bot:   Cancelled. Send a new order or type help for commands.
```

---

## 6. Payment Tracking Flow

### View Pending Balances

```
User:  unpaid   (also: who owes / pending)

Bot:   💰 Pending balances:

       1. Priya — Rs.900 pending (total Rs.1200, paid Rs.300)
          Chocolate cake · Due 13 Apr

       2. Meena — Rs.2000 pending (total Rs.2500, paid Rs.500)
          Bridal appointment · Due 20 Apr

       Total pending: Rs.2,900

       To mark as collected:
       paid 1 · paid Priya · paid all
```

### Mark as Collected

| Command | Bot Response |
|---|---|
| `paid 1` | ✅ Rs.900 collected from Priya. 💰 |
| `paid Priya` | Marks all orders for "Priya" as collected |
| `paid all` | ✅ All balances cleared! Rs.2,900 collected. 💰 |

---

## 7. Earnings / Income Flow

```
User:  earnings   (also: income / earnings last month)

Bot:   📊 Earnings — March 2026

       💰 Total collected: Rs.12,500
       📦 Orders completed: 14
       📈 Avg per order: Rs.893

       Top customers:
         • Priya — Rs.2,400 (2 orders)
         • Meena — Rs.2,000 (1 order)
         • Rahul — Rs.1,800 (1 order)

       Reply unpaid to see pending balances.
       Reply earnings last month to compare.
```

### Commands

| Command | Description |
|---|---|
| `earnings` | Current month's collected income, order count, avg per order, top customers |
| `earnings last month` | Previous calendar month's earnings for comparison |
| `income` | Alias for earnings |

---

## 8. Subscription & Trial Flow

### Trial Nudge Messages (Sent Automatically)

```
Bot:   ⏳ Hey Anita, your free trial ends in 5 days.

       To keep using Awesist after that, subscribe for just Rs.99/month.

       Reply subscribe anytime to get your payment link.
```
> Sent at: 5 days, 3 days, and 1 day before expiry.

### Trial Expired — Full Flow

```
User:  [Sends any message after trial expires]

Bot:   Hi Anita 👋

       Your free trial has ended.

       Here's what you did during your trial:
       📦 14 orders/appointments saved in total
       🗓️  8 added this month
       ⏰  3 upcoming orders still waiting for reminders
       💰 Rs.12,500 collected overall
       📈 Rs.4,200 collected this month
       💸 Rs.2,900 still to collect from customers

       Awesist costs just 0.8% of what you've already collected.

       Keep all of this going for just Rs.99/month — less than Rs.4 a day!

       👉 Pay here: [Razorpay link]

       Your data is safe and will be waiting for you. 🔒

User:  subscribe   (also: pay / renew / subscription)

Bot:   Hi Anita 👋

       Subscribe to Awesist for just Rs.99/month — that's less than Rs.4 a day!

       👉 Pay here: [Razorpay link]

       Your data is safe and will be waiting for you. 🔒

       --- [User pays via Razorpay] ---

Bot:   ✅ Payment received! Welcome aboard, Anita. 🎉

       Your Awesist subscription is active for the next 30 days.

       Add an order:  Priya cake 15th April 5pm
       reminders   — see all upcoming orders
       unpaid      — check pending balances
       earnings    — see this month's collections

       Type how anytime to see message examples.
```

> **Technical note:** Payment is processed via Razorpay. Webhook at `/razorpay-webhook` is called on payment success. HMAC-SHA256 signature verification used for security. Subscription activated for 30 days from payment date.

---

## 9. Automated Background Flows

### A. Reminder Worker (Runs Every 30 Seconds)

**Vendor Message** — sent to business owner when reminder time is reached:

```
⏰ Reminder

Chocolate cake for Priya
📅 Due: 13 Apr 2026 5:00 PM
💰 Balance pending: Rs.900

Reply paid Priya when collected.
```

**Customer Messages by Business Type** — sent to end customer:

| Business Type | Customer Message |
|---|---|
| Baker | Hi! 🎂 Your order from Anita's Bakery is ready on 13 Apr 2026. Balance due: Rs.900. Please carry the exact amount. Thank you! |
| Salon | Hi! ✂️ Reminder from Anita's Salon — your appointment is on 13 Apr 2026. Balance due: Rs.900. See you soon! |
| Tailor | Hi! 🧵 Your clothes from Ravi Tailors will be ready on 13 Apr 2026. Balance due: Rs.900. Please collect at your convenience. |
| Tiffin | Hi! 🍱 Your tiffin order from Sharma Tiffin is confirmed for 13 Apr 2026. Balance due: Rs.900. |
| Photography | Hi! 📸 Reminder from Priya Studios — your session is on 13 Apr 2026. Balance due: Rs.900. Looking forward to it! |
| Generic | Hi! Reminder from [Business Name] — [task]. Date: 13 Apr 2026. Balance due: Rs.900. |

### B. Morning Summary Worker (Daily at 8 AM)

**With reminders today:**

```
Good morning, Anita! ☀️

Today — 13 Apr 2026 (2 reminders):

1. Chocolate cake for Priya  ⏰ 10:00 AM
2. Meena bridal appointment  ⏰ 2:00 PM

Coming up:
• Wedding cake for Rahul — 14 Apr 11:00 AM
• Cupcakes for Sneha — 15 Apr 5:00 PM

Reply reminders to see all · help for commands
```

**No reminders today:**

```
Good morning, Anita! ☀️

No reminders today — enjoy the break! ☕

Coming up:
• Priya cake — 14 Apr 5:00 PM

Reply reminders to see all · help for commands
```

---

## 10. Help, Examples & Error Handling

### A. Commands Menu

**Trigger:** `help` / `menu` / `commands` / `?`

```
Bot:   🤖 Awesist Commands

       Add an order or appointment:
         Just type it naturally — date, time, customer number, amount

       📋 reminders       → see your reminders
       💰 unpaid          → see pending balances
       ✅ paid <n/name>   → mark collected
       ✅ paid all        → clear all balances
       ❌ delete <number> → delete a reminder
       🚫 cancel          → cancel current action

       Reply how to see message examples
```

### B. Examples

**Trigger:** `how` / `example` / `examples` / `format` / `how to`

```
Bot:   💡 How to add orders — examples

       Minimal (just date required):
         Priya cake 13th April 5pm

       With customer notification:
         Priya cake 13th April 5pm 9876543210
         (I'll WhatsApp Priya when the order is due)

       With payment tracking:
         Priya cake 13th April 5pm total 1200 advance 300

       Full — everything in one message:
         Send chocolate cake to Priya on 13th April at 5pm.
         Her number is 9876543210. Total Rs 1200, she paid Rs 300 advance.

       I understand: today, tomorrow, next Monday, 13th April, 5pm, evening...
       Hindi/Hinglish also works!
```

### C. Greeting Responses

**Trigger:** `hi` / `hello` / `hey` / `hii` / `good morning` / `namaste` / `namaskar`

**If mid-conversation:**
```
Bot:   Hi! 👋

       We were in the middle of saving Priya cake.

       Want to continue or start fresh?

       Reply: continue · cancel
```

**If no active state:**
```
Bot:   Hi! 👋 Here's how to use Awesist:

       Save an order or appointment:
         Send cake to Priya on 13th April at 6pm
         Meena's bridal appointment tomorrow at 10am

       Check your orders:
         reminders → see all upcoming
         unpaid    → see pending balances

       Mark as collected:
         paid Priya  or  paid 1

       Track your income:
         earnings           → this month's collections
         earnings last month → previous month

       how  → see message examples
       help → see all commands
```

### D. Error Messages

| Trigger | Bot Response |
|---|---|
| Invalid date/time | ⚠️ Couldn't understand that. Try: tomorrow at 6pm or 13th April 3pm |
| Due date too soon (<30 mins) | ⚠️ Due date is too soon — please set it at least 30 minutes in the future. |
| Invalid phone number | ⚠️ Couldn't read that number. Send a 10-digit number like 9876543210 · or skip |
| Invalid amount | ⚠️ Couldn't understand that amount. Send a number like 850 · or skip |
| Reminder not found | ⚠️ Reminder not found. Send reminders to see your list. |
| Non-English/Indic script | Sorry, I currently only understand English. Please send your message in English. |
| Unrecognised intent | 🤔 I didn't quite get that. Try: Send cake to Priya on 13th April... · reminders · unpaid · earnings · delete 2. Type how to see examples · help for all commands. |

### E. Silently Ignored Messages (No Response)

| Message | Reason |
|---|---|
| ok, okay, thanks, thank you | Filler/acknowledgement |
| got it, noted, sure, great | Filler/acknowledgement |
| 👍 🙏 | Reaction emojis |
| Any message under 3 characters | Too short to be meaningful |

---

## 11. WhatsApp Message Templates

Pre-approved templates for outbound messages. Cost: ~Rs.0.50 vs Rs.5-8 for regular messages.

> **Savings:** Using templates for reminders and morning summary saves ~90% on WhatsApp API costs.

---

### Template 1: `vendor_order_reminder`
**Category:** Utility

**Body:**
```
⏰ *Reminder*

{{1}}
📅 Due: {{2}}
💰 Balance pending: Rs.{{3}}

Reply *paid {{4}}* when collected.
```

| Variable | Sample Value |
|---|---|
| `{{1}}` | Chocolate cake for Priya |
| `{{2}}` | 13 Apr 2026, 5:00 PM |
| `{{3}}` | 900 |
| `{{4}}` | Priya |

---

### Template 2: `morning_summary`
**Category:** Utility

**Body:**
```
Good morning, {{1}}! ☀️

Today — {{2}} ({{3}} reminder(s)):
{{4}}

Reply *reminders* to see all your orders.
```

| Variable | Sample Value |
|---|---|
| `{{1}}` | Anita |
| `{{2}}` | 13 Apr 2026 |
| `{{3}}` | 3 |
| `{{4}}` | 1. Chocolate cake for Priya — 10:00 AM 2. Meena bridal — 2:00 PM |

> ⚠️ Meta may reject templates with lists in a single variable. If rejected, split into separate templates.

---

### Template 3: `customer_order_reminder_baker`
**Category:** Utility

**Body:**
```
Hi! 🎂 Your order from {{1}} is ready on {{2}}. Balance due: Rs.{{3}}. Please carry the exact amount. Thank you!
```

| Variable | Sample Value |
|---|---|
| `{{1}}` | Anita's Bakery |
| `{{2}}` | 13 Apr 2026 |
| `{{3}}` | 900 |

---

### Template 4: `customer_appointment_reminder`
**Category:** Utility

**Body:**
```
Hi! Reminder from {{1}} — your appointment is on {{2}}. Balance due: Rs.{{3}}. See you soon!
```

| Variable | Sample Value |
|---|---|
| `{{1}}` | Anita's Salon |
| `{{2}}` | 13 Apr 2026 |
| `{{3}}` | 900 |

---

### Template 5: `trial_expiry_nudge`
**Category:** Utility

**Body:**
```
Hey {{1}}, your free trial ends in {{2}} days.

To keep using Awesist after that, subscribe for just Rs.99/month.

Reply *subscribe* anytime to get your payment link.
```

| Variable | Sample Value |
|---|---|
| `{{1}}` | Anita |
| `{{2}}` | 5 |

---

## Quick Reference — All Commands

| Command | What it Does |
|---|---|
| `reminders` | List all upcoming reminders |
| `unpaid` | See all pending balances |
| `paid <number>` | Mark reminder #N as paid |
| `paid <name>` | Mark all orders for customer as paid |
| `paid all` | Clear all pending balances |
| `delete <number>` | Delete reminder #N |
| `earnings` | Current month income summary |
| `earnings last month` | Previous month income |
| `subscribe` | Get Razorpay payment link |
| `edit` | Edit the last saved reminder |
| `cancel` | Cancel current in-progress action |
| `help` | Show commands menu |
| `how` | Show message examples |

---

*Awesist — Never forget an order again. 🎂*
