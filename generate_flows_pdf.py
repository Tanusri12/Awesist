from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak,
    Table, TableStyle, HRFlowable
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER

OUTPUT = "/Users/troy/Documents/AI/Awesist/Awesist_User_Flows.pdf"

# ── Colours ──────────────────────────────────────────────────────────────────
GREEN      = colors.HexColor("#25D366")   # WhatsApp green
DARK_GREEN = colors.HexColor("#128C7E")
LIGHT_BG   = colors.HexColor("#F0FFF4")
GREY_BG    = colors.HexColor("#F5F5F5")
DARK_TEXT  = colors.HexColor("#1A1A1A")
MID_GREY   = colors.HexColor("#666666")
BUBBLE_BOT = colors.HexColor("#E8F5E9")
BUBBLE_USR = colors.HexColor("#DCF8C6")
WARN       = colors.HexColor("#FFF3CD")
WARN_BDR   = colors.HexColor("#FFC107")

# ── Document ─────────────────────────────────────────────────────────────────
doc = SimpleDocTemplate(
    OUTPUT, pagesize=A4,
    leftMargin=2*cm, rightMargin=2*cm,
    topMargin=2*cm, bottomMargin=2*cm
)

styles = getSampleStyleSheet()

# Custom styles
def S(name, **kw):
    return ParagraphStyle(name, **kw)

cover_title  = S("CoverTitle",  fontSize=32, leading=40, textColor=DARK_GREEN,
                  alignment=TA_CENTER, fontName="Helvetica-Bold")
cover_sub    = S("CoverSub",    fontSize=14, leading=20, textColor=MID_GREY,
                  alignment=TA_CENTER)
cover_date   = S("CoverDate",   fontSize=11, textColor=MID_GREY,
                  alignment=TA_CENTER)

h1           = S("H1",          fontSize=18, leading=24, textColor=DARK_GREEN,
                  fontName="Helvetica-Bold", spaceAfter=6)
h2           = S("H2",          fontSize=14, leading=18, textColor=DARK_GREEN,
                  fontName="Helvetica-Bold", spaceBefore=10, spaceAfter=4)
h3           = S("H3",          fontSize=12, leading=16, textColor=DARK_TEXT,
                  fontName="Helvetica-Bold", spaceBefore=6, spaceAfter=3)

body         = S("Body",        fontSize=10, leading=15, textColor=DARK_TEXT)
body_small   = S("BodySmall",   fontSize=9,  leading=13, textColor=MID_GREY)
bullet_style = S("Bullet",      fontSize=10, leading=14, textColor=DARK_TEXT,
                  leftIndent=16, bulletIndent=4)
code_style   = S("Code",        fontSize=9,  leading=13,
                  fontName="Courier", textColor=colors.HexColor("#333333"),
                  backColor=GREY_BG, leftIndent=8)
bot_msg      = S("BotMsg",      fontSize=9,  leading=13, textColor=DARK_TEXT,
                  fontName="Courier", backColor=BUBBLE_BOT,
                  leftIndent=10, rightIndent=10)
user_msg     = S("UserMsg",     fontSize=9,  leading=13, textColor=DARK_TEXT,
                  fontName="Courier", backColor=BUBBLE_USR,
                  leftIndent=10, rightIndent=10)
label_green  = S("LabelGreen",  fontSize=8,  textColor=DARK_GREEN,
                  fontName="Helvetica-Bold")
label_grey   = S("LabelGrey",   fontSize=8,  textColor=MID_GREY,
                  fontName="Helvetica-Bold")

story = []

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────
def sp(n=1):
    return Spacer(1, n * 0.4 * cm)

def hr():
    return HRFlowable(width="100%", thickness=1, color=colors.HexColor("#E0E0E0"),
                      spaceAfter=4, spaceBefore=4)

def section_hr():
    return HRFlowable(width="100%", thickness=2, color=GREEN,
                      spaceAfter=6, spaceBefore=8)

def bot(text):
    """Render a bot chat bubble."""
    lines = [Paragraph('<font color="#128C7E"><b>Bot</b></font>', label_green)]
    for line in text.strip().split("\n"):
        safe = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        lines.append(Paragraph(safe, bot_msg))
    return lines

def user(text):
    """Render a user chat bubble."""
    lines = [Paragraph('<font color="#555555"><b>User</b></font>', label_grey)]
    for line in text.strip().split("\n"):
        safe = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        lines.append(Paragraph(safe, user_msg))
    return lines

def cmd_table(rows):
    """Command reference table."""
    data = [["Command / Trigger", "Bot Response / Action"]] + rows
    t = Table(data, colWidths=[6*cm, 10*cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), DARK_GREEN),
        ("TEXTCOLOR",  (0,0), (-1,0), colors.white),
        ("FONTNAME",   (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE",   (0,0), (-1,-1), 9),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, GREY_BG]),
        ("GRID",       (0,0), (-1,-1), 0.5, colors.HexColor("#CCCCCC")),
        ("VALIGN",     (0,0), (-1,-1), "TOP"),
        ("LEFTPADDING",(0,0), (-1,-1), 6),
        ("RIGHTPADDING",(0,0),(-1,-1), 6),
        ("TOPPADDING", (0,0), (-1,-1), 4),
        ("BOTTOMPADDING",(0,0),(-1,-1), 4),
    ]))
    return t

def flow_table(steps):
    """Step-by-step flow table."""
    data = [["Step", "Who", "Message / Action"]] + steps
    t = Table(data, colWidths=[0.8*cm, 1.8*cm, 13.4*cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), DARK_GREEN),
        ("TEXTCOLOR",  (0,0), (-1,0), colors.white),
        ("FONTNAME",   (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE",   (0,0), (-1,-1), 9),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, GREY_BG]),
        ("GRID",       (0,0), (-1,-1), 0.5, colors.HexColor("#CCCCCC")),
        ("VALIGN",     (0,0), (-1,-1), "TOP"),
        ("ALIGN",      (0,0), (0,-1),  "CENTER"),
        ("LEFTPADDING",(0,0), (-1,-1), 5),
        ("RIGHTPADDING",(0,0),(-1,-1), 5),
        ("TOPPADDING", (0,0), (-1,-1), 4),
        ("BOTTOMPADDING",(0,0),(-1,-1), 4),
    ]))
    return t

def note_box(text, color=WARN, border=WARN_BDR):
    t = Table([[Paragraph(text, body_small)]], colWidths=[16*cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), color),
        ("BOX",        (0,0), (-1,-1), 1, border),
        ("LEFTPADDING",(0,0), (-1,-1), 8),
        ("RIGHTPADDING",(0,0),(-1,-1), 8),
        ("TOPPADDING", (0,0), (-1,-1), 6),
        ("BOTTOMPADDING",(0,0),(-1,-1), 6),
    ]))
    return t

# =============================================================================
# COVER PAGE
# =============================================================================
story += [
    sp(4),
    Paragraph("Awesist", cover_title),
    sp(0.5),
    Paragraph("WhatsApp Bot — Complete User Flow Document", cover_sub),
    sp(0.5),
    Paragraph("Version 1.0  |  March 2026", cover_date),
    sp(2),
    HRFlowable(width="60%", thickness=3, color=GREEN, hAlign="CENTER",
               spaceAfter=20, spaceBefore=20),
    sp(1),
]

# Summary table on cover
summary_data = [
    ["Total Flows Documented", "10"],
    ["Commands Covered", "20+"],
    ["Business Types Supported", "5 (Baker, Salon, Tailor, Tiffin, Photography)"],
    ["Languages", "English (Hinglish accepted)"],
    ["Platform", "WhatsApp Business API"],
]
st = Table(summary_data, colWidths=[8*cm, 8*cm])
st.setStyle(TableStyle([
    ("BACKGROUND", (0,0), (-1,-1), LIGHT_BG),
    ("FONTNAME",   (0,0), (0,-1), "Helvetica-Bold"),
    ("FONTSIZE",   (0,0), (-1,-1), 10),
    ("GRID",       (0,0), (-1,-1), 0.5, GREEN),
    ("LEFTPADDING",(0,0), (-1,-1), 10),
    ("TOPPADDING", (0,0), (-1,-1), 6),
    ("BOTTOMPADDING",(0,0),(-1,-1), 6),
    ("ALIGN",      (1,0), (1,-1),  "CENTER"),
]))
story.append(st)
story.append(PageBreak())

# =============================================================================
# TABLE OF CONTENTS
# =============================================================================
story.append(Paragraph("Table of Contents", h1))
story.append(hr())

toc = [
    ("1", "Onboarding Flow", "New user registration and business setup"),
    ("2", "Reminder Creation — Fast Path", "Single-message order/appointment entry"),
    ("3", "Reminder Creation — Slow Path", "Step-by-step guided entry"),
    ("4", "Edit Reminder Flow", "Updating saved reminders"),
    ("5", "List & Delete Reminders", "Viewing and removing reminders"),
    ("6", "Payment Tracking Flow", "Tracking balances and marking paid"),
    ("7", "Earnings / Income Flow", "Monthly income summary"),
    ("8", "Subscription & Trial Flow", "Free trial, nudges, and Razorpay payment"),
    ("9", "Automated Background Flows", "Morning summary and reminder worker"),
    ("10", "Help, Examples & Error Handling", "Commands menu, examples, and error messages"),
]

toc_data = [["#", "Flow Name", "Description"]] + toc
toc_table = Table(toc_data, colWidths=[0.8*cm, 5.5*cm, 9.7*cm])
toc_table.setStyle(TableStyle([
    ("BACKGROUND",   (0,0), (-1,0), DARK_GREEN),
    ("TEXTCOLOR",    (0,0), (-1,0), colors.white),
    ("FONTNAME",     (0,0), (-1,0), "Helvetica-Bold"),
    ("FONTSIZE",     (0,0), (-1,-1), 10),
    ("ROWBACKGROUNDS",(0,1),(-1,-1), [colors.white, GREY_BG]),
    ("GRID",         (0,0), (-1,-1), 0.5, colors.HexColor("#CCCCCC")),
    ("VALIGN",       (0,0), (-1,-1), "TOP"),
    ("LEFTPADDING",  (0,0), (-1,-1), 6),
    ("TOPPADDING",   (0,0), (-1,-1), 5),
    ("BOTTOMPADDING",(0,0), (-1,-1), 5),
    ("FONTNAME",     (1,1), (1,-1), "Helvetica-Bold"),
    ("TEXTCOLOR",    (1,1), (1,-1), DARK_GREEN),
]))
story.append(toc_table)
story.append(PageBreak())

# =============================================================================
# FLOW 1 — ONBOARDING
# =============================================================================
story.append(Paragraph("Flow 1: Onboarding", h1))
story.append(section_hr())
story.append(Paragraph(
    "Triggered when a new phone number sends its first message to the bot. "
    "Collects business name and auto-detects business type using AI.",
    body))
story.append(sp())

story.append(Paragraph("Step-by-Step Flow", h2))
story.append(flow_table([
    ["1", "User", "Sends any first message (e.g. 'Hi')"],
    ["2", "Bot",  "Hi! I'm Awesist — I make sure you never forget an order or appointment.\n\nWhat's your business name?"],
    ["3", "User", "Anita's Bakery"],
    ["4", "Bot",  "Done! You're all set, Anita's Bakery.\n\nYour 30-day free trial starts now — no card needed.\n\n[Sends business-specific onboarding example]"],
]))
story.append(sp())

story.append(Paragraph("Onboarding Examples by Business Type", h2))
bt_data = [
    ["Business Type", "Example Message Shown"],
    ["Baker",       "Send chocolate cake to Priya on 13th April at 5pm.\nHer number is 9876543210. Total Rs 1200, she paid Rs 300 advance."],
    ["Salon",       "Meena's bridal appointment on 20th April at 11am.\nHer number 9876543210. Charge Rs 2500, advance Rs 500 received."],
    ["Tailor",      "Ravi suit delivery 25th April at 6pm.\nHis number 9876543210. Total Rs 3500, advance Rs 1000 paid."],
    ["Tiffin",      "Sharma ji monthly tiffin starts 1st May.\nHis number 9876543210. Total Rs 1800, advance Rs 900 diya."],
    ["Photography", "Priya pre-wedding shoot 15th April at 9am.\nHer number 9876543210. Total Rs 8000, advance Rs 3000 received."],
    ["Default",     "Send report to Ravi on 20th April at 5pm.\nHis number 9876543210. Total Rs 5000, advance Rs 2000 paid."],
]
bt = Table(bt_data, colWidths=[3*cm, 13*cm])
bt.setStyle(TableStyle([
    ("BACKGROUND",   (0,0), (-1,0), DARK_GREEN),
    ("TEXTCOLOR",    (0,0), (-1,0), colors.white),
    ("FONTNAME",     (0,0), (-1,0), "Helvetica-Bold"),
    ("FONTSIZE",     (0,0), (-1,-1), 9),
    ("ROWBACKGROUNDS",(0,1),(-1,-1), [colors.white, GREY_BG]),
    ("GRID",         (0,0), (-1,-1), 0.5, colors.HexColor("#CCCCCC")),
    ("VALIGN",       (0,0), (-1,-1), "TOP"),
    ("LEFTPADDING",  (0,0), (-1,-1), 6),
    ("TOPPADDING",   (0,0), (-1,-1), 4),
    ("BOTTOMPADDING",(0,0), (-1,-1), 4),
    ("FONTNAME",     (1,1), (1,-1), "Courier"),
    ("FONTSIZE",     (1,1), (1,-1), 8),
]))
story.append(bt)
story.append(sp())
story.append(note_box(
    "Validation: Business name must be at least 2 characters. "
    "Business type is auto-detected by AI from the name. "
    "A 30-day free trial starts immediately — no card required."
))
story.append(PageBreak())

# =============================================================================
# FLOW 2 — REMINDER CREATION FAST PATH
# =============================================================================
story.append(Paragraph("Flow 2: Reminder Creation — Fast Path", h1))
story.append(section_hr())
story.append(Paragraph(
    "When a user sends a single message containing date AND time, the bot extracts "
    "everything automatically and saves the reminder in one step.",
    body))
story.append(sp())

story.append(Paragraph("Scenario A — Full Details in One Message", h2))
story.append(flow_table([
    ["1", "User", "Send chocolate cake to Priya on 13th April at 5pm.\nHer number is 9876543210. Total Rs 1200, she paid Rs 300 advance."],
    ["2", "Bot",  "All saved!\n\nChocolate cake for Priya\nDue: 13 Apr 2026 5:00 PM\nReminder: 13 Apr 3:00 PM (2 hrs before)\nRs.300 advance · Rs.900 balance pending\nCustomer will be notified on the due date.\n\nReply unpaid to see pending balances · edit to update this"],
]))
story.append(sp())

story.append(Paragraph("Scenario B — Date/Time Only (No Payment)", h2))
story.append(flow_table([
    ["1", "User", "Priya cake 13th April 5pm"],
    ["2", "Bot",  "Saved!\n\nPriya cake\nDue: 13 Apr 2026 5:00 PM\nReminder: 13 Apr 3:00 PM (2 hrs before)\n\nReply unpaid to track payments · reminders to see all · edit to update this"],
]))
story.append(sp())

story.append(Paragraph("Scenario C — With Phone, No Payment", h2))
story.append(flow_table([
    ["1", "User", "Priya cake 13th April 5pm 9876543210"],
    ["2", "Bot",  "Reminder set!\n\nPriya cake\nDue: 13 Apr 2026 5:00 PM\nReminder: 13 Apr 3:00 PM\n\nWhat's the total order amount?\nReply with amount e.g. 850 · or skip"],
    ["3", "User", "1200"],
    ["4", "Bot",  "Total: Rs.1200\n\nAdvance received?\nReply with amount e.g. 300 · no advance · full (fully paid)"],
    ["5", "User", "300"],
    ["6", "Bot",  "All saved!\n\nPriya cake\nDue: 13 Apr 2026 5:00 PM\nReminder: 13 Apr 3:00 PM\nRs.300 advance · Rs.900 balance pending\n\nReply unpaid anytime to see pending balances."],
]))
story.append(sp())

story.append(Paragraph("Reminder Time Calculation Rules", h2))
rt_data = [
    ["Condition", "Reminder Set To"],
    ["2+ hours before due time available", "Due time minus 2 hours"],
    ["Less than 2 hours but 1+ min available", "Due time minus 1 minute"],
    ["Due time is in the past", "30 seconds from now"],
    ["Reminder would equal due time", "1 minute before due"],
]
rt = Table(rt_data, colWidths=[8*cm, 8*cm])
rt.setStyle(TableStyle([
    ("BACKGROUND",   (0,0), (-1,0), DARK_GREEN),
    ("TEXTCOLOR",    (0,0), (-1,0), colors.white),
    ("FONTNAME",     (0,0), (-1,0), "Helvetica-Bold"),
    ("FONTSIZE",     (0,0), (-1,-1), 9),
    ("ROWBACKGROUNDS",(0,1),(-1,-1), [colors.white, GREY_BG]),
    ("GRID",         (0,0), (-1,-1), 0.5, colors.HexColor("#CCCCCC")),
    ("LEFTPADDING",  (0,0), (-1,-1), 6),
    ("TOPPADDING",   (0,0), (-1,-1), 4),
    ("BOTTOMPADDING",(0,0), (-1,-1), 4),
]))
story.append(rt)
story.append(sp())
story.append(note_box(
    "Validation: Due date/time must be at least 30 minutes in the future. "
    "Phone numbers must be 10-digit Indian numbers starting with 6, 7, 8, or 9. "
    "They are stored as 91XXXXXXXXXX (with country code)."
))
story.append(PageBreak())

# =============================================================================
# FLOW 3 — SLOW PATH
# =============================================================================
story.append(Paragraph("Flow 3: Reminder Creation — Slow Path", h1))
story.append(section_hr())
story.append(Paragraph(
    "When a user's message has a task but missing date/time, the bot guides them "
    "step-by-step through each missing piece.",
    body))
story.append(sp())

story.append(Paragraph("Step-by-Step Flow", h2))
story.append(flow_table([
    ["1", "User", "Priya cake"],
    ["2", "Bot",  "Fill in the date and send back:\n\nTask: Priya cake\nDate: [e.g. 13 Apr 6pm]\nPhone: [optional]\nTotal: [optional]\nAdvance: [optional]"],
    ["3", "User", "Task: Priya cake\nDate: 13 Apr 5pm\nPhone: 9876543210\nTotal: 1200\nAdvance: 300"],
    ["4", "Bot",  "All saved! (same as Fast Path confirmation)"],
]))
story.append(sp())

story.append(Paragraph("Alternative: Bot Asks for Time Separately", h2))
story.append(flow_table([
    ["1", "User", "Priya cake tomorrow"],
    ["2", "Bot",  "When should I remind you?\n\nReply: 2 hrs before · day before · or a specific time like 1pm"],
    ["3", "User", "2 hrs before"],
    ["4", "Bot",  "Customer's WhatsApp number?\n\nI'll send them a reminder too.\n\ne.g. 9876543210 · or skip to not notify them"],
    ["5", "User", "skip"],
    ["6", "Bot",  "What's the total order amount?\n\nReply with amount e.g. 850 · or skip"],
    ["7", "User", "skip"],
    ["8", "Bot",  "Saved!\n\nPriya cake\nDue: 14 Apr 2026 12:00 PM\nReminder: 14 Apr 10:00 AM"],
]))
story.append(sp())

story.append(Paragraph("Generic Reminder Trigger (Meta Commands)", h2))
story.append(Paragraph(
    'If user sends generic phrases like "set a reminder", "create reminder", "add order":',
    body))
story.append(sp(0.5))
for line in [
    "Just tell me the order details directly — no need for commands!",
    "",
    "Examples:",
    "  Priya cake 13th April 5pm",
    "  Meena blouse stitching 20th April at 11am total 800",
    "",
    "Type how to see more examples.",
]:
    story.append(Paragraph(line.replace("&","&amp;"), code_style))
story.append(PageBreak())

# =============================================================================
# FLOW 4 — EDIT REMINDER
# =============================================================================
story.append(Paragraph("Flow 4: Edit Reminder Flow", h1))
story.append(section_hr())
story.append(Paragraph(
    "After saving a reminder, the user can immediately edit it by replying 'edit'. "
    "The bot re-parses the new message and updates the existing record.",
    body))
story.append(sp())

story.append(flow_table([
    ["1", "Bot",  "All saved!\n\nPriya cake\nDue: 13 Apr 5:00 PM\nReminder: 13 Apr 3:00 PM\n...\n\nReply edit to update this"],
    ["2", "User", "edit"],
    ["3", "Bot",  "Update reminder\n\nSend the corrected details:\n\nPriya cake 15th April 6pm\nMeena appointment 20th April at 11am total 2500 advance 500"],
    ["4", "User", "Priya cake 15th April 6pm total 1200 advance 500"],
    ["5", "Bot",  "All saved!\n\nPriya cake\nDue: 15 Apr 2026 6:00 PM\nReminder: 15 Apr 4:00 PM\nRs.500 advance · Rs.700 balance pending"],
]))
story.append(sp())
story.append(note_box(
    "The edit flow updates the existing reminder in the database rather than creating a new one. "
    "Payment details are also updated if amounts are provided in the edit message. "
    "Edit is only available immediately after saving (state: just_saved)."
))
story.append(PageBreak())

# =============================================================================
# FLOW 5 — LIST & DELETE
# =============================================================================
story.append(Paragraph("Flow 5: List & Delete Reminders", h1))
story.append(section_hr())
story.append(sp())

story.append(Paragraph("List All Reminders", h2))
story.append(flow_table([
    ["1", "User", "reminders  (also: my reminders / list / show reminders)"],
    ["2", "Bot",  "Your reminders:\n\n1. Priya cake\n   Remind: 13 Apr 2026 3:00 PM\n   Due: 13 Apr 2026 5:00 PM\n\n2. Meena appointment\n   Remind: 20 Apr 2026 9:00 AM\n   Due: 20 Apr 2026 11:00 AM\n\nReply: delete <number> · unpaid to see balances"],
]))
story.append(sp())

story.append(Paragraph("Delete a Reminder", h2))
story.append(flow_table([
    ["1", "User", "delete 1"],
    ["2", "Bot",  "Reminder deleted."],
]))
story.append(sp())

story.append(Paragraph("Cancel Current Action", h2))
story.append(flow_table([
    ["1", "User", "cancel"],
    ["2", "Bot",  "Cancelled. Send a new order or type help for commands."],
]))
story.append(PageBreak())

# =============================================================================
# FLOW 6 — PAYMENT TRACKING
# =============================================================================
story.append(Paragraph("Flow 6: Payment Tracking Flow", h1))
story.append(section_hr())
story.append(Paragraph(
    "Track who owes money, mark balances as collected, and view all pending payments.",
    body))
story.append(sp())

story.append(Paragraph("View Pending Balances", h2))
story.append(flow_table([
    ["1", "User", "unpaid  (also: who owes / pending)"],
    ["2", "Bot",  "Pending balances:\n\n1. Priya — Rs.900 pending (total Rs.1200, paid Rs.300)\n   Chocolate cake · Due 13 Apr\n\n2. Meena — Rs.2000 pending (total Rs.2500, paid Rs.500)\n   Bridal appointment · Due 20 Apr\n\nTotal pending: Rs.2900\n\nTo mark as collected:\npaid 1 · paid Priya · paid all"],
]))
story.append(sp())

story.append(Paragraph("Mark as Collected", h2))
story.append(cmd_table([
    ["paid 1",    "Marks order #1 as collected. Bot: 'Rs.900 collected from Priya.'"],
    ["paid Priya","Marks all orders for 'Priya' as collected."],
    ["paid all",  "Clears all pending balances. Bot: 'All balances cleared! Rs.2900 collected.'"],
]))
story.append(PageBreak())

# =============================================================================
# FLOW 7 — EARNINGS
# =============================================================================
story.append(Paragraph("Flow 7: Earnings / Income Flow", h1))
story.append(section_hr())
story.append(sp())

story.append(flow_table([
    ["1", "User", "earnings  (also: income / earnings last month)"],
    ["2", "Bot",  "Earnings — March 2026\n\nTotal collected: Rs.12,500\nOrders completed: 14\nAvg per order: Rs.893\n\nTop customers:\n  Priya — Rs.2,400 (2 orders)\n  Meena — Rs.2,000 (1 order)\n  Rahul — Rs.1,800 (1 order)\n\nReply unpaid to see pending balances.\nReply earnings last month to compare."],
]))
story.append(sp())

story.append(Paragraph("Commands", h2))
story.append(cmd_table([
    ["earnings",            "Shows current month's collected income, order count, avg per order, top customers."],
    ["earnings last month", "Shows previous calendar month's earnings for comparison."],
    ["income",              "Alias for 'earnings'."],
]))
story.append(PageBreak())

# =============================================================================
# FLOW 8 — SUBSCRIPTION & TRIAL
# =============================================================================
story.append(Paragraph("Flow 8: Subscription & Trial Flow", h1))
story.append(section_hr())
story.append(Paragraph(
    "Awesist offers a 30-day free trial. After expiry, users are prompted to subscribe "
    "at Rs.99/month via Razorpay.",
    body))
story.append(sp())

story.append(Paragraph("Trial Nudge Messages", h2))
story.append(flow_table([
    ["—", "Bot",  "5 days before expiry:\n\nHey Anita, your free trial ends in 5 days.\n\nTo keep using Awesist after that, subscribe for just Rs.99/month.\n\nReply subscribe anytime to get your payment link."],
    ["—", "Bot",  "(Same message repeated at 3 days and 1 day remaining)"],
]))
story.append(sp())

story.append(Paragraph("Trial Expired — Subscribe Flow", h2))
story.append(flow_table([
    ["1", "User", "(Sends any message after trial expires)"],
    ["2", "Bot",  "Hi Anita\n\nYour free trial has ended.\n\nHere's what you did during your trial:\n  14 orders/appointments saved in total\n  8 added this month\n  3 upcoming orders still waiting for reminders\n  Rs.12,500 collected overall\n  Rs.4,200 collected this month\n  Rs.2,900 still to collect from customers\n\nAwesist costs just 0.8% of what you've already collected.\n\nKeep all of this going for just Rs.99/month — less than Rs.4 a day!\n\nPay here: [Razorpay link]\n\nYour data is safe and will be waiting for you."],
    ["3", "User", "subscribe  (also: pay / renew / subscription)"],
    ["4", "Bot",  "Hi Anita\n\nSubscribe to Awesist for just Rs.99/month — that's less than Rs.4 a day!\n\nPay here: [Razorpay link]\n\nYour data is safe and will be waiting for you."],
    ["5", "—",    "User pays via Razorpay link"],
    ["6", "Bot",  "Payment received! Welcome aboard, Anita.\n\nYour Awesist subscription is active for the next 30 days.\n\nAdd an order: Priya cake 15th April 5pm\nreminders — see all upcoming orders\nunpaid — check pending balances\nearnings — see this month's collections\n\nType how anytime to see message examples."],
]))
story.append(sp())
story.append(note_box(
    "Payment is processed via Razorpay. The webhook at /razorpay-webhook is called on "
    "successful payment. HMAC-SHA256 signature verification is used for security. "
    "Subscription is activated for 30 days from payment date."
))
story.append(PageBreak())

# =============================================================================
# FLOW 9 — BACKGROUND WORKERS
# =============================================================================
story.append(Paragraph("Flow 9: Automated Background Flows", h1))
story.append(section_hr())
story.append(Paragraph(
    "Two background workers run automatically: the Reminder Worker (every 30 seconds) "
    "and the Morning Summary Worker (daily at 8 AM).",
    body))
story.append(sp())

story.append(Paragraph("A. Reminder Worker — Vendor Message", h2))
story.append(Paragraph(
    "Sent to the business owner when their reminder time is reached:", body_small))
story.append(sp(0.5))
for line in [
    "Reminder",
    "",
    "Chocolate cake for Priya",
    "Due: 13 Apr 2026 5:00 PM",
    "Balance pending: Rs.900",
    "",
    "Reply paid Priya when collected.",
]:
    story.append(Paragraph(line, code_style))
story.append(sp())

story.append(Paragraph("B. Reminder Worker — Customer Messages by Business Type", h2))
ct_data = [
    ["Business Type", "Customer WhatsApp Message"],
    ["Baker",       "Hi! Your order from Anita's Bakery is ready on 13 Apr 2026. Balance due: Rs.900. Please carry the exact amount. Thank you!"],
    ["Salon",       "Hi! Reminder from Anita's Salon — your appointment is on 13 Apr 2026. Balance due: Rs.900. See you soon!"],
    ["Tailor",      "Hi! Your clothes from Ravi Tailors will be ready on 13 Apr 2026. Balance due: Rs.900. Please collect at your convenience."],
    ["Tiffin",      "Hi! Your tiffin order from Sharma Tiffin is confirmed for 13 Apr 2026. Balance due: Rs.900."],
    ["Photography", "Hi! Reminder from Priya Studios — your session is on 13 Apr 2026. Balance due: Rs.900. Looking forward to it!"],
    ["Generic",     "Hi! Reminder from [Business Name] — [task]. Date: 13 Apr 2026. Balance due: Rs.900."],
]
ct = Table(ct_data, colWidths=[3*cm, 13*cm])
ct.setStyle(TableStyle([
    ("BACKGROUND",   (0,0), (-1,0), DARK_GREEN),
    ("TEXTCOLOR",    (0,0), (-1,0), colors.white),
    ("FONTNAME",     (0,0), (-1,0), "Helvetica-Bold"),
    ("FONTSIZE",     (0,0), (-1,-1), 9),
    ("ROWBACKGROUNDS",(0,1),(-1,-1), [colors.white, GREY_BG]),
    ("GRID",         (0,0), (-1,-1), 0.5, colors.HexColor("#CCCCCC")),
    ("VALIGN",       (0,0), (-1,-1), "TOP"),
    ("LEFTPADDING",  (0,0), (-1,-1), 6),
    ("TOPPADDING",   (0,0), (-1,-1), 4),
    ("BOTTOMPADDING",(0,0), (-1,-1), 4),
]))
story.append(ct)
story.append(sp())

story.append(Paragraph("C. Morning Summary Worker (Daily at 8 AM)", h2))
story.append(Paragraph("Sent to all users with morning summary enabled:", body_small))
story.append(sp(0.5))
for line in [
    "Good morning, Anita!",
    "",
    "Today — 13 Apr 2026 (2 reminders):",
    "",
    "1. Chocolate cake for Priya  10:00 AM",
    "2. Meena bridal appointment  2:00 PM",
    "",
    "Coming up:",
    "  Wedding cake for Rahul — 14 Apr 11:00 AM",
    "  Cupcakes for Sneha — 15 Apr 5:00 PM",
    "",
    "Reply reminders to see all · help for commands",
]:
    story.append(Paragraph(line, code_style))
story.append(sp(0.5))
story.append(Paragraph("If no reminders today:", body_small))
story.append(sp(0.5))
for line in [
    "Good morning, Anita!",
    "",
    "No reminders today — enjoy the break!",
    "",
    "Coming up:",
    "  Priya cake — 14 Apr 5:00 PM",
    "",
    "Reply reminders to see all · help for commands",
]:
    story.append(Paragraph(line, code_style))
story.append(PageBreak())

# =============================================================================
# FLOW 10 — HELP, EXAMPLES, ERRORS
# =============================================================================
story.append(Paragraph("Flow 10: Help, Examples & Error Handling", h1))
story.append(section_hr())
story.append(sp())

story.append(Paragraph("A. Help / Commands Menu", h2))
story.append(Paragraph("Trigger: help / menu / commands / ?", body_small))
story.append(sp(0.5))
for line in [
    "Awesist Commands",
    "",
    "Add an order or appointment:",
    "  Just type it naturally — date, time, customer number, amount",
    "",
    "reminders       - see your reminders",
    "unpaid          - see pending balances",
    "paid <n/name>   - mark collected",
    "paid all        - clear all balances",
    "delete <number> - delete a reminder",
    "cancel          - cancel current action",
    "",
    "Reply how to see message examples",
]:
    story.append(Paragraph(line, code_style))
story.append(sp())

story.append(Paragraph("B. Examples / How-To", h2))
story.append(Paragraph("Trigger: how / example / examples / format / how to", body_small))
story.append(sp(0.5))
for line in [
    "How to add orders — examples",
    "",
    "Minimal (just date required):",
    "  Priya cake 13th April 5pm",
    "",
    "With customer notification:",
    "  Priya cake 13th April 5pm 9876543210",
    "",
    "With payment tracking:",
    "  Priya cake 13th April 5pm total 1200 advance 300",
    "",
    "Full — everything in one message:",
    "  Send chocolate cake to Priya on 13th April at 5pm.",
    "  Her number is 9876543210. Total Rs 1200, she paid Rs 300.",
    "",
    "I understand: today, tomorrow, next Monday, 13th April, 5pm, evening...",
    "Hindi/Hinglish also works!",
]:
    story.append(Paragraph(line, code_style))
story.append(sp())

story.append(Paragraph("C. Greeting Responses", h2))
story.append(Paragraph(
    "Trigger: hi / hello / hey / hii / good morning / namaste / namaskar", body_small))
story.append(sp(0.5))

story.append(Paragraph("If mid-conversation:", body_small))
story.append(sp(0.3))
for line in [
    "Hi!",
    "",
    "We were in the middle of saving Priya cake.",
    "",
    "Want to continue or start fresh?",
    "",
    "Reply: continue · cancel",
]:
    story.append(Paragraph(line, code_style))
story.append(sp(0.5))

story.append(Paragraph("If no active state:", body_small))
story.append(sp(0.3))
for line in [
    "Hi! Here's how to use Awesist:",
    "",
    "Save an order or appointment:",
    "  Send cake to Priya on 13th April at 6pm",
    "",
    "Check your orders:",
    "  reminders - see all upcoming",
    "  unpaid    - see pending balances",
    "",
    "Mark as collected:",
    "  paid Priya  or  paid 1",
    "",
    "Track your income:",
    "  earnings           - this month's collections",
    "  earnings last month - previous month",
    "",
    "how  - see message examples",
    "help - see all commands",
]:
    story.append(Paragraph(line, code_style))
story.append(sp())

story.append(Paragraph("D. Error Messages", h2))
story.append(cmd_table([
    ["Invalid date/time",       "Couldn't understand that. Try: tomorrow at 6pm or 13th April 3pm"],
    ["Due date too soon",       "Due date is too soon — please set it at least 30 minutes in the future."],
    ["Invalid phone number",    "Couldn't read that number. Send a 10-digit number like 9876543210 · or skip"],
    ["Invalid amount",          "Couldn't understand that amount. Send a number like 850 · or skip"],
    ["Reminder not found",      "Reminder not found. Send reminders to see your list."],
    ["Non-English message",     "Sorry, I currently only understand English. Please send your message in English."],
    ["Unrecognised intent",     "I didn't quite get that.\n\nTry: Send cake to Priya on 13th April at 6pm\nreminders · unpaid · earnings · delete 2\n\nType how to see examples · help for all commands."],
]))
story.append(sp())

story.append(Paragraph("E. Silently Ignored Messages", h2))
story.append(Paragraph(
    "The following messages receive NO response from the bot:", body))
story.append(sp(0.5))
ig_data = [
    ["Message", "Reason"],
    ["ok, okay, thanks, thank you", "Filler/acknowledgement — no action needed"],
    ["got it, noted, sure, great", "Filler/acknowledgement — no action needed"],
    ["(thumbs up emoji), (pray emoji)", "Reaction emojis — no action needed"],
    ["Any message under 3 characters", "Too short to be a meaningful command"],
]
igt = Table(ig_data, colWidths=[8*cm, 8*cm])
igt.setStyle(TableStyle([
    ("BACKGROUND",   (0,0), (-1,0), DARK_GREEN),
    ("TEXTCOLOR",    (0,0), (-1,0), colors.white),
    ("FONTNAME",     (0,0), (-1,0), "Helvetica-Bold"),
    ("FONTSIZE",     (0,0), (-1,-1), 9),
    ("ROWBACKGROUNDS",(0,1),(-1,-1), [colors.white, GREY_BG]),
    ("GRID",         (0,0), (-1,-1), 0.5, colors.HexColor("#CCCCCC")),
    ("LEFTPADDING",  (0,0), (-1,-1), 6),
    ("TOPPADDING",   (0,0), (-1,-1), 4),
    ("BOTTOMPADDING",(0,0), (-1,-1), 4),
]))
story.append(igt)
story.append(PageBreak())

# =============================================================================
# WHATSAPP TEMPLATE REFERENCE
# =============================================================================
story.append(Paragraph("Appendix: WhatsApp Message Templates", h1))
story.append(section_hr())
story.append(Paragraph(
    "These are the pre-approved Meta message templates required to send outbound "
    "messages outside the 24-hour user-initiated window at reduced cost (~Rs.0.50 vs Rs.5-8).",
    body))
story.append(sp())

templates = [
    ("vendor_order_reminder", "Utility", [
        "Reminder",
        "",
        "{{1}}",
        "Due: {{2}}",
        "Balance pending: Rs.{{3}}",
        "",
        "Reply paid {{4}} when collected.",
    ], [
        ("{{1}}", "Chocolate cake for Priya"),
        ("{{2}}", "13 Apr 2026, 5:00 PM"),
        ("{{3}}", "900"),
        ("{{4}}", "Priya"),
    ]),
    ("morning_summary", "Utility", [
        "Good morning, {{1}}!",
        "",
        "Today - {{2}} ({{3}} reminder(s)):",
        "{{4}}",
        "",
        "Reply reminders to see all your orders.",
    ], [
        ("{{1}}", "Anita"),
        ("{{2}}", "13 Apr 2026"),
        ("{{3}}", "3"),
        ("{{4}}", "1. Chocolate cake for Priya - 10:00 AM  2. Meena bridal - 2:00 PM"),
    ]),
    ("customer_order_reminder_baker", "Utility", [
        "Hi! Your order from {{1}} is ready on {{2}}.",
        "Balance due: Rs.{{3}}.",
        "Please carry the exact amount. Thank you!",
    ], [
        ("{{1}}", "Anita's Bakery"),
        ("{{2}}", "13 Apr 2026"),
        ("{{3}}", "900"),
    ]),
    ("customer_appointment_reminder", "Utility", [
        "Hi! Reminder from {{1}} - your appointment is on {{2}}.",
        "Balance due: Rs.{{3}}. See you soon!",
    ], [
        ("{{1}}", "Anita's Salon"),
        ("{{2}}", "13 Apr 2026"),
        ("{{3}}", "900"),
    ]),
    ("trial_expiry_nudge", "Utility", [
        "Hey {{1}}, your free trial ends in {{2}} days.",
        "",
        "To keep using Awesist after that, subscribe for just Rs.99/month.",
        "",
        "Reply subscribe anytime to get your payment link.",
    ], [
        ("{{1}}", "Anita"),
        ("{{2}}", "5"),
    ]),
]

for tname, tcat, tlines, tvars in templates:
    story.append(Paragraph(tname, h3))
    story.append(Paragraph(f"Category: {tcat}", body_small))
    story.append(sp(0.3))
    for line in tlines:
        story.append(Paragraph(line if line else " ", code_style))
    story.append(sp(0.3))
    var_data = [["Variable", "Sample Value"]] + [[v, s] for v, s in tvars]
    vt = Table(var_data, colWidths=[3*cm, 13*cm])
    vt.setStyle(TableStyle([
        ("BACKGROUND",   (0,0), (-1,0), colors.HexColor("#128C7E")),
        ("TEXTCOLOR",    (0,0), (-1,0), colors.white),
        ("FONTNAME",     (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE",     (0,0), (-1,-1), 9),
        ("ROWBACKGROUNDS",(0,1),(-1,-1), [colors.white, BUBBLE_BOT]),
        ("GRID",         (0,0), (-1,-1), 0.5, colors.HexColor("#CCCCCC")),
        ("LEFTPADDING",  (0,0), (-1,-1), 6),
        ("TOPPADDING",   (0,0), (-1,-1), 3),
        ("BOTTOMPADDING",(0,0), (-1,-1), 3),
    ]))
    story.append(vt)
    story.append(sp())

story.append(note_box(
    "Cost comparison: Regular outbound message = Rs.5-8 per conversation. "
    "Approved template message = ~Rs.0.50 per conversation. "
    "Using templates for morning summary and reminders saves ~90% on WhatsApp API costs. "
    "Templates require Meta approval (3-5 business days)."
))

# =============================================================================
# BUILD
# =============================================================================
doc.build(story)
print(f"PDF saved to: {OUTPUT}")
