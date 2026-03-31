const pptxgen = require("pptxgenjs");
const pres = new pptxgen();
pres.layout = "LAYOUT_16x9";
pres.title = "Awesist System Architecture";

// ── Colours ────────────────────────────────────────────────────────────────
const G_DARK   = "075E54";   // WhatsApp dark green
const G_MED    = "128C7E";   // WhatsApp medium green
const G_LIGHT  = "25D366";   // WhatsApp bright green
const G_BG     = "DCF8C6";   // WhatsApp bubble green
const NAVY     = "1A2744";
const SLATE    = "2C3E50";
const WHITE    = "FFFFFF";
const OFF_W    = "F8FFFE";
const GREY     = "95A5A6";
const LGREY    = "ECF0F1";
const ORANGE   = "E67E22";
const BLUE     = "2980B9";
const PURPLE   = "8E44AD";
const RED      = "E74C3C";
const TEAL     = "16A085";

const makeShadow = () => ({ type: "outer", blur: 8, offset: 3, angle: 135, color: "000000", opacity: 0.12 });

// ═══════════════════════════════════════════════════════════════════════════
// SLIDE 1 — COVER
// ═══════════════════════════════════════════════════════════════════════════
{
  const s = pres.addSlide();
  s.background = { color: G_DARK };

  // Green accent bar on left
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 0.3, h: 5.625, fill: { color: G_LIGHT }, line: { color: G_LIGHT } });

  // WhatsApp-style bubble decoration top-right
  s.addShape(pres.shapes.OVAL, { x: 8.5, y: -0.3, w: 2.5, h: 2.5, fill: { color: G_MED, transparency: 70 }, line: { color: G_MED, transparency: 70 } });
  s.addShape(pres.shapes.OVAL, { x: 9.2, y: 3.8, w: 1.8, h: 1.8, fill: { color: G_LIGHT, transparency: 75 }, line: { color: G_LIGHT, transparency: 75 } });

  // Title
  s.addText("Awesist", { x: 0.6, y: 1.3, w: 8, h: 1.1, fontSize: 54, bold: true, color: WHITE, fontFace: "Arial Black", margin: 0 });
  s.addText("System Architecture", { x: 0.6, y: 2.4, w: 8, h: 0.6, fontSize: 24, color: G_BG, fontFace: "Arial", margin: 0 });

  // Divider
  s.addShape(pres.shapes.RECTANGLE, { x: 0.6, y: 3.1, w: 4, h: 0.04, fill: { color: G_LIGHT }, line: { color: G_LIGHT } });

  // Subtitle
  s.addText("WhatsApp Business Bot for Indian SMBs", { x: 0.6, y: 3.3, w: 8, h: 0.4, fontSize: 14, color: GREY, fontFace: "Arial", margin: 0 });
  s.addText("AWS EC2  ·  Supabase  ·  Razorpay  ·  Meta WhatsApp API", { x: 0.6, y: 3.75, w: 8, h: 0.35, fontSize: 11, color: GREY, fontFace: "Arial", margin: 0 });

  // Version
  s.addText("March 2026  |  v1.0", { x: 0.6, y: 4.9, w: 5, h: 0.3, fontSize: 9, color: GREY, fontFace: "Arial", margin: 0 });
}

// ═══════════════════════════════════════════════════════════════════════════
// SLIDE 2 — FULL SYSTEM ARCHITECTURE
// ═══════════════════════════════════════════════════════════════════════════
{
  const s = pres.addSlide();
  s.background = { color: "F0F4F8" };

  // Title bar
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 10, h: 0.55, fill: { color: G_DARK }, line: { color: G_DARK } });
  s.addText("Awesist — Full System Architecture", { x: 0.2, y: 0, w: 9, h: 0.55, fontSize: 16, bold: true, color: WHITE, valign: "middle", margin: 0 });

  // ── LAYER LABELS ──────────────────────────────────────────────────────

  // USERS layer label
  s.addText("USERS", { x: 0.08, y: 0.85, w: 0.7, h: 1.2, fontSize: 7, bold: true, color: WHITE, fontFace: "Arial",
    rotate: 270, align: "center", valign: "middle",
    fill: { color: GREY }, margin: 0 });

  // META / WHATSAPP layer
  s.addText("META API", { x: 0.08, y: 2.15, w: 0.7, h: 0.9, fontSize: 7, bold: true, color: WHITE, fontFace: "Arial",
    rotate: 270, align: "center", valign: "middle",
    fill: { color: "1877F2" }, margin: 0 });

  // AWS EC2 layer
  s.addText("AWS EC2", { x: 0.08, y: 3.1, w: 0.7, h: 1.9, fontSize: 7, bold: true, color: WHITE, fontFace: "Arial",
    rotate: 270, align: "center", valign: "middle",
    fill: { color: ORANGE }, margin: 0 });

  // SERVICES layer
  s.addText("SERVICES", { x: 0.08, y: 5.1, w: 0.7, h: 0.35, fontSize: 6, bold: true, color: WHITE, fontFace: "Arial",
    rotate: 270, align: "center", valign: "middle",
    fill: { color: PURPLE }, margin: 0 });

  // ── ROW 1: USERS ──────────────────────────────────────────────────────
  const userBoxes = [
    ["Baker", G_LIGHT],
    ["Salon", G_LIGHT],
    ["Tailor", G_LIGHT],
    ["Tiffin", G_LIGHT],
    ["Photographer", G_LIGHT],
  ];
  userBoxes.forEach(([label, color], i) => {
    const x = 1.0 + i * 1.78;
    s.addShape(pres.shapes.RECTANGLE, { x, y: 0.75, w: 1.55, h: 0.55,
      fill: { color }, line: { color: G_MED, width: 1.5 }, shadow: makeShadow() });
    s.addText(label, { x, y: 0.75, w: 1.55, h: 0.55, fontSize: 10, bold: true,
      color: G_DARK, align: "center", valign: "middle", margin: 0 });
  });

  // Arrow down: Users → WhatsApp
  s.addShape(pres.shapes.LINE, { x: 5.0, y: 1.3, w: 0, h: 0.3, line: { color: G_MED, width: 1.5, endArrowType: "arrow" } });
  s.addText("WhatsApp Message", { x: 4.0, y: 1.3, w: 2, h: 0.25, fontSize: 6.5, color: GREY, align: "center", margin: 0 });

  // ── ROW 2: META WHATSAPP API ──────────────────────────────────────────
  s.addShape(pres.shapes.RECTANGLE, { x: 1.0, y: 1.65, w: 8.1, h: 0.65,
    fill: { color: "1877F2" }, line: { color: "0D5FD6", width: 1.5 }, shadow: makeShadow() });
  s.addText([
    { text: "Meta WhatsApp Business API", options: { bold: true } },
    { text: "    |    Webhook: POST /webhook    |    Phone Number ID    |    Token Auth" }
  ], { x: 1.0, y: 1.65, w: 8.1, h: 0.65, fontSize: 10, color: WHITE, align: "center", valign: "middle", margin: 0 });

  // Arrow: Meta → EC2
  s.addShape(pres.shapes.LINE, { x: 5.0, y: 2.3, w: 0, h: 0.25, line: { color: "1877F2", width: 1.5, endArrowType: "arrow" } });

  // ── ROW 3: AWS EC2 — FastAPI App ─────────────────────────────────────
  // EC2 outer container
  s.addShape(pres.shapes.RECTANGLE, { x: 0.82, y: 2.55, w: 8.4, h: 1.95,
    fill: { color: "FFF8F0" }, line: { color: ORANGE, width: 1.5 }, shadow: makeShadow() });

  // FastAPI header
  s.addShape(pres.shapes.RECTANGLE, { x: 0.82, y: 2.55, w: 8.4, h: 0.32,
    fill: { color: ORANGE }, line: { color: ORANGE } });
  s.addText("FastAPI Application  (uvicorn  ·  port 8000)  —  systemd service", {
    x: 0.82, y: 2.55, w: 8.4, h: 0.32, fontSize: 9, bold: true, color: WHITE, align: "center", valign: "middle", margin: 0 });

  // Internal boxes inside EC2
  const ec2Boxes = [
    { x: 0.95, label: "Message\nRouter", color: TEAL },
    { x: 2.45, label: "Onboarding\nHandler", color: G_MED },
    { x: 3.95, label: "Reminder\nHandler", color: G_MED },
    { x: 5.45, label: "Payment\nHandler", color: G_MED },
    { x: 6.95, label: "Subscription\nService", color: PURPLE },
    { x: 8.45, label: "Reminder\nWorker", color: RED },
  ];
  ec2Boxes.forEach(({ x, label, color }) => {
    s.addShape(pres.shapes.RECTANGLE, { x, y: 2.95, w: 1.38, h: 0.7,
      fill: { color }, line: { color, width: 1 }, shadow: makeShadow() });
    s.addText(label, { x, y: 2.95, w: 1.38, h: 0.7, fontSize: 8, bold: true, color: WHITE,
      align: "center", valign: "middle", margin: 0 });
  });

  // Arrows between internal boxes
  [0.95, 2.45, 3.95, 5.45, 6.95].forEach(x => {
    s.addShape(pres.shapes.LINE, { x: x + 1.38, y: 3.3, w: 0.07, h: 0, line: { color: GREY, width: 1, endArrowType: "arrow" } });
  });

  // Morning Summary Worker (below)
  s.addShape(pres.shapes.RECTANGLE, { x: 0.95, y: 3.78, w: 2.5, h: 0.55,
    fill: { color: "E74C3C" }, line: { color: "C0392B", width: 1 }, shadow: makeShadow() });
  s.addText("Morning Summary Worker\n(Daily 8 AM  ·  every user)", { x: 0.95, y: 3.78, w: 2.5, h: 0.55,
    fontSize: 7.5, bold: true, color: WHITE, align: "center", valign: "middle", margin: 0 });

  // Conversation Memory
  s.addShape(pres.shapes.RECTANGLE, { x: 4.0, y: 3.78, w: 2.2, h: 0.55,
    fill: { color: SLATE }, line: { color: NAVY, width: 1 }, shadow: makeShadow() });
  s.addText("Conversation\nMemory (in-memory)", { x: 4.0, y: 3.78, w: 2.2, h: 0.55,
    fontSize: 7.5, bold: true, color: WHITE, align: "center", valign: "middle", margin: 0 });

  // AI Extractor
  s.addShape(pres.shapes.RECTANGLE, { x: 6.8, y: 3.78, w: 2.2, h: 0.55,
    fill: { color: "8E44AD" }, line: { color: "6C3483", width: 1 }, shadow: makeShadow() });
  s.addText("AI Extractor\n(Claude Haiku)", { x: 6.8, y: 3.78, w: 2.2, h: 0.55,
    fontSize: 7.5, bold: true, color: WHITE, align: "center", valign: "middle", margin: 0 });

  // Nginx label (left of EC2)
  s.addShape(pres.shapes.RECTANGLE, { x: 0.82, y: 2.55, w: 0.0, h: 0, fill: { color: OFF_W }, line: { color: OFF_W } });
  s.addText("Nginx\n(SSL proxy)", { x: 0.0, y: 2.7, w: 0.82, h: 0.5, fontSize: 7, color: ORANGE, align: "center", bold: true, margin: 0 });
  s.addText("DuckDNS", { x: 0.0, y: 3.2, w: 0.82, h: 0.3, fontSize: 7, color: GREY, align: "center", margin: 0 });

  // ── ROW 4: EXTERNAL SERVICES ──────────────────────────────────────────
  const svcY = 5.12;
  const services = [
    { x: 1.0,  w: 2.2, label: "Supabase\n(PostgreSQL)", color: "3ECF8E", sub: "Users · Reminders\nPayments · Sessions" },
    { x: 3.5,  w: 2.2, label: "Razorpay", color: "2D81FF", sub: "Payment Links\nWebhook /razorpay-webhook" },
    { x: 6.0,  w: 2.0, label: "DuckDNS", color: "F39C12", sub: "awesist.duckdns.org\nFree HTTPS domain" },
    { x: 8.3,  w: 1.55, label: "Let's Encrypt", color: "003A70", sub: "SSL Certificate\n(Certbot auto-renew)" },
  ];
  services.forEach(({ x, w, label, color, sub }) => {
    s.addShape(pres.shapes.RECTANGLE, { x, y: svcY, w, h: 0.6,
      fill: { color }, line: { color, width: 1.5 }, shadow: makeShadow() });
    s.addText(label, { x, y: svcY, w, h: 0.32, fontSize: 9, bold: true, color: WHITE, align: "center", valign: "middle", margin: 0 });
    s.addText(sub, { x, y: svcY + 0.3, w, h: 0.3, fontSize: 6.5, color: WHITE, align: "center", valign: "middle", margin: 2 });
  });

  // Arrows: EC2 → Services
  [[2.1, "DB"], [4.6, "Pay"], [7.0, "DNS"]].forEach(([x, label]) => {
    s.addShape(pres.shapes.LINE, { x, y: 4.5, w: 0, h: 0.62, line: { color: GREY, width: 1, endArrowType: "arrow", dashType: "dash" } });
    s.addText(label, { x: x - 0.15, y: 4.55, w: 0.4, h: 0.2, fontSize: 6, color: GREY, align: "center", margin: 0 });
  });

  // Arrow: EC2 → Meta (outbound messages)
  s.addShape(pres.shapes.LINE, { x: 7.5, y: 2.3, w: 0, h: 0.25, line: { color: G_LIGHT, width: 1.5, endArrowType: "arrow", dashType: "dash" } });
  s.addText("Send Msg", { x: 7.6, y: 2.32, w: 0.8, h: 0.2, fontSize: 6, color: G_MED, margin: 0 });

  // Footer
  s.addText("AWS EC2 t2.micro (free tier)  ·  Ubuntu 22.04  ·  Python 3.12  ·  FastAPI  ·  Systemd", {
    x: 0, y: 5.45, w: 10, h: 0.2, fontSize: 7, color: GREY, align: "center", margin: 0 });
}

// ═══════════════════════════════════════════════════════════════════════════
// SLIDE 3 — MESSAGE PROCESSING FLOW
// ═══════════════════════════════════════════════════════════════════════════
{
  const s = pres.addSlide();
  s.background = { color: "F8FFFE" };

  // Title
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 10, h: 0.55, fill: { color: G_DARK }, line: { color: G_DARK } });
  s.addText("Message Processing Flow", { x: 0.2, y: 0, w: 9, h: 0.55, fontSize: 16, bold: true, color: WHITE, valign: "middle", margin: 0 });

  // Flow steps — vertical pipeline on left
  const steps = [
    { label: "1. User sends WhatsApp message", color: G_LIGHT, textColor: G_DARK },
    { label: "2. Meta delivers to /webhook (POST)", color: "1877F2", textColor: WHITE },
    { label: "3. Verify webhook signature (VERIFY_TOKEN)", color: SLATE, textColor: WHITE },
    { label: "4. Extract phone + message text", color: SLATE, textColor: WHITE },
    { label: "5. Ignore? (ok/thanks/short msg)", color: ORANGE, textColor: WHITE },
    { label: "6. Check subscription status", color: PURPLE, textColor: WHITE },
    { label: "7. Is onboarded? → Onboarding handler", color: G_MED, textColor: WHITE },
    { label: "8. Route intent: reminder / order / command / AI", color: TEAL, textColor: WHITE },
    { label: "9. Handler processes → saves to Supabase", color: RED, textColor: WHITE },
    { label: "10. Send WhatsApp reply via Meta API", color: G_LIGHT, textColor: G_DARK },
  ];

  steps.forEach(({ label, color, textColor }, i) => {
    const x = 0.5;
    const y = 0.7 + i * 0.47;
    const w = 5.2;
    const h = 0.38;
    s.addShape(pres.shapes.RECTANGLE, { x, y, w, h,
      fill: { color }, line: { color, width: 1 }, shadow: makeShadow() });
    s.addText(label, { x, y, w, h, fontSize: 9, bold: true, color: textColor,
      align: "left", valign: "middle", margin: 8 });
    // Arrow to next step
    if (i < steps.length - 1) {
      s.addShape(pres.shapes.LINE, { x: x + w / 2, y: y + h, w: 0, h: 0.09,
        line: { color: GREY, width: 1, endArrowType: "arrow" } });
    }
  });

  // ── Right side: Route Decision Tree ──────────────────────────────────
  s.addShape(pres.shapes.RECTANGLE, { x: 6.0, y: 0.65, w: 3.8, h: 4.7,
    fill: { color: WHITE }, line: { color: LGREY, width: 1 }, shadow: makeShadow() });
  s.addShape(pres.shapes.RECTANGLE, { x: 6.0, y: 0.65, w: 3.8, h: 0.35,
    fill: { color: TEAL }, line: { color: TEAL } });
  s.addText("Intent Router", { x: 6.0, y: 0.65, w: 3.8, h: 0.35, fontSize: 10, bold: true,
    color: WHITE, align: "center", valign: "middle", margin: 0 });

  const routes = [
    { label: "remind / reminder", handler: "Reminder Handler", color: G_MED },
    { label: "order / deliver / buy", handler: "Order Router", color: G_MED },
    { label: "unpaid / who owes", handler: "Payment Handler", color: BLUE },
    { label: "earnings / income", handler: "Earnings Handler", color: BLUE },
    { label: "reminders / list", handler: "List Handler", color: TEAL },
    { label: "help / menu / how", handler: "Commands Handler", color: SLATE },
    { label: "subscribe / pay", handler: "Subscription Service", color: PURPLE },
    { label: "anything else", handler: "AI Classifier", color: RED },
  ];

  routes.forEach(({ label, handler, color }, i) => {
    const y = 1.1 + i * 0.52;
    // Trigger box
    s.addShape(pres.shapes.RECTANGLE, { x: 6.1, y, w: 1.5, h: 0.35,
      fill: { color: LGREY }, line: { color: GREY, width: 0.5 } });
    s.addText(label, { x: 6.1, y, w: 1.5, h: 0.35, fontSize: 7.5, color: SLATE,
      align: "center", valign: "middle", margin: 2 });
    // Arrow
    s.addShape(pres.shapes.LINE, { x: 7.6, y: y + 0.175, w: 0.3, h: 0,
      line: { color: GREY, width: 1, endArrowType: "arrow" } });
    // Handler box
    s.addShape(pres.shapes.RECTANGLE, { x: 7.9, y, w: 1.8, h: 0.35,
      fill: { color }, line: { color, width: 0.5 }, shadow: makeShadow() });
    s.addText(handler, { x: 7.9, y, w: 1.8, h: 0.35, fontSize: 7.5, bold: true, color: WHITE,
      align: "center", valign: "middle", margin: 2 });
  });

  // Footer note
  s.addText("All handlers read/write from Supabase (PostgreSQL via psycopg2 connection pool)", {
    x: 0.3, y: 5.35, w: 9.5, h: 0.2, fontSize: 7.5, color: GREY, align: "center", margin: 0 });
}

// ═══════════════════════════════════════════════════════════════════════════
// SLIDE 4 — BACKGROUND WORKERS + SUBSCRIPTION FLOW
// ═══════════════════════════════════════════════════════════════════════════
{
  const s = pres.addSlide();
  s.background = { color: "F8FFFE" };

  // Title
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 10, h: 0.55, fill: { color: G_DARK }, line: { color: G_DARK } });
  s.addText("Background Workers & Subscription Flow", { x: 0.2, y: 0, w: 9, h: 0.55, fontSize: 16, bold: true, color: WHITE, valign: "middle", margin: 0 });

  // ── LEFT: Reminder Worker ─────────────────────────────────────────────
  s.addShape(pres.shapes.RECTANGLE, { x: 0.3, y: 0.7, w: 4.3, h: 2.35,
    fill: { color: WHITE }, line: { color: RED, width: 2 }, shadow: makeShadow() });
  s.addShape(pres.shapes.RECTANGLE, { x: 0.3, y: 0.7, w: 4.3, h: 0.38,
    fill: { color: RED }, line: { color: RED } });
  s.addText("Reminder Worker  (every 30 seconds)", { x: 0.3, y: 0.7, w: 4.3, h: 0.38,
    fontSize: 10, bold: true, color: WHITE, align: "center", valign: "middle", margin: 0 });

  const rwSteps = [
    "Poll DB: reminder_time <= NOW()",
    "Lock row → mark as processing",
    "Send vendor WhatsApp message",
    "Send customer reminder (if phone saved)",
    "Mark reminder as sent in DB",
  ];
  rwSteps.forEach((step, i) => {
    const y = 1.18 + i * 0.36;
    s.addShape(pres.shapes.RECTANGLE, { x: 0.5, y, w: 3.9, h: 0.28,
      fill: { color: "FFF5F5" }, line: { color: RED, width: 0.5 } });
    s.addText(`${i + 1}. ${step}`, { x: 0.5, y, w: 3.9, h: 0.28, fontSize: 8.5,
      color: SLATE, align: "left", valign: "middle", margin: 6 });
    if (i < rwSteps.length - 1) {
      s.addShape(pres.shapes.LINE, { x: 2.45, y: y + 0.28, w: 0, h: 0.08,
        line: { color: RED, width: 1, endArrowType: "arrow" } });
    }
  });

  // ── RIGHT: Morning Summary Worker ────────────────────────────────────
  s.addShape(pres.shapes.RECTANGLE, { x: 5.4, y: 0.7, w: 4.3, h: 2.35,
    fill: { color: WHITE }, line: { color: ORANGE, width: 2 }, shadow: makeShadow() });
  s.addShape(pres.shapes.RECTANGLE, { x: 5.4, y: 0.7, w: 4.3, h: 0.38,
    fill: { color: ORANGE }, line: { color: ORANGE } });
  s.addText("Morning Summary Worker  (daily 8 AM)", { x: 5.4, y: 0.7, w: 4.3, h: 0.38,
    fontSize: 10, bold: true, color: WHITE, align: "center", valign: "middle", margin: 0 });

  const msSteps = [
    "Check: current hour == 8 AM",
    "Fetch users: morning_summary_enabled=TRUE",
    "Skip if summary already sent today",
    "Build today's reminders + upcoming list",
    "Send WhatsApp summary → mark sent",
  ];
  msSteps.forEach((step, i) => {
    const y = 1.18 + i * 0.36;
    s.addShape(pres.shapes.RECTANGLE, { x: 5.6, y, w: 3.9, h: 0.28,
      fill: { color: "FFF8F0" }, line: { color: ORANGE, width: 0.5 } });
    s.addText(`${i + 1}. ${step}`, { x: 5.6, y, w: 3.9, h: 0.28, fontSize: 8.5,
      color: SLATE, align: "left", valign: "middle", margin: 6 });
    if (i < msSteps.length - 1) {
      s.addShape(pres.shapes.LINE, { x: 7.55, y: y + 0.28, w: 0, h: 0.08,
        line: { color: ORANGE, width: 1, endArrowType: "arrow" } });
    }
  });

  // ── BOTTOM: Subscription Flow ─────────────────────────────────────────
  s.addShape(pres.shapes.RECTANGLE, { x: 0.3, y: 3.2, w: 9.4, h: 2.2,
    fill: { color: WHITE }, line: { color: PURPLE, width: 2 }, shadow: makeShadow() });
  s.addShape(pres.shapes.RECTANGLE, { x: 0.3, y: 3.2, w: 9.4, h: 0.35,
    fill: { color: PURPLE }, line: { color: PURPLE } });
  s.addText("Subscription & Trial Flow", { x: 0.3, y: 3.2, w: 9.4, h: 0.35,
    fontSize: 10, bold: true, color: WHITE, align: "center", valign: "middle", margin: 0 });

  const subSteps = [
    { label: "Trial\nStarts", sub: "30 days\nfree", color: G_LIGHT, textColor: G_DARK },
    { label: "Nudge\n7 days", sub: "gentle\nheads-up", color: G_MED, textColor: WHITE },
    { label: "Nudge\n5 days", sub: "value\nstats", color: G_MED, textColor: WHITE },
    { label: "Nudge\n3 days", sub: "urgency\nmsg", color: ORANGE, textColor: WHITE },
    { label: "Nudge\n1 day", sub: "final\nwarning", color: RED, textColor: WHITE },
    { label: "Trial\nExpired", sub: "stats +\nRazorpay link", color: SLATE, textColor: WHITE },
    { label: "User\nPays ₹99", sub: "Razorpay\nwebhook", color: "2D81FF", textColor: WHITE },
    { label: "Active\n30 days", sub: "subscription\nextended", color: G_LIGHT, textColor: G_DARK },
  ];

  subSteps.forEach(({ label, sub, color, textColor }, i) => {
    const x = 0.5 + i * 1.17;
    const y = 3.63;
    s.addShape(pres.shapes.RECTANGLE, { x, y, w: 1.02, h: 0.65,
      fill: { color }, line: { color, width: 1 }, shadow: makeShadow() });
    s.addText(label, { x, y, w: 1.02, h: 0.38, fontSize: 8, bold: true, color: textColor,
      align: "center", valign: "middle", margin: 0 });
    s.addText(sub, { x, y: y + 0.36, w: 1.02, h: 0.3, fontSize: 6.5, color: textColor,
      align: "center", valign: "middle", margin: 0 });
    if (i < subSteps.length - 1) {
      s.addShape(pres.shapes.LINE, { x: x + 1.02, y: y + 0.325, w: 0.15, h: 0,
        line: { color: GREY, width: 1, endArrowType: "arrow" } });
    }
  });

  // Renewal label
  s.addText("Renewal: same flow — subscription stacks if renewed before expiry", {
    x: 0.5, y: 4.38, w: 9, h: 0.25, fontSize: 7.5, color: GREY, align: "center",
    italic: true, margin: 0 });

  // Footer
  s.addText("Razorpay webhook  POST /razorpay-webhook  →  HMAC-SHA256 verified  →  activate_subscription(phone, months=1)", {
    x: 0, y: 5.38, w: 10, h: 0.2, fontSize: 7, color: GREY, align: "center", margin: 0 });
}

// ═══════════════════════════════════════════════════════════════════════════
// SLIDE 5 — DATABASE SCHEMA
// ═══════════════════════════════════════════════════════════════════════════
{
  const s = pres.addSlide();
  s.background = { color: "F0F4F8" };

  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 10, h: 0.55, fill: { color: G_DARK }, line: { color: G_DARK } });
  s.addText("Database Schema (Supabase / PostgreSQL)", { x: 0.2, y: 0, w: 9, h: 0.55, fontSize: 16, bold: true, color: WHITE, valign: "middle", margin: 0 });

  const tables = [
    {
      name: "users", color: "3ECF8E", x: 0.2, y: 0.7, w: 3.0,
      cols: ["id (phone)", "business_name", "business_type", "trial_started_at", "is_paid",
             "subscription_expires_at", "last_payment_link_id", "morning_summary_enabled", "last_summary_sent_at"],
    },
    {
      name: "reminders", color: G_MED, x: 3.55, y: 0.7, w: 3.0,
      cols: ["id", "user_id → users.id", "task", "due_date", "due_time",
             "reminder_time", "customer_phone", "sent (bool)", "created_at"],
    },
    {
      name: "payments", color: BLUE, x: 6.9, y: 0.7, w: 2.9,
      cols: ["id", "reminder_id → reminders.id", "user_id → users.id",
             "customer_name", "total", "advance", "balance", "paid (bool)", "created_at"],
    },
  ];

  tables.forEach(({ name, color, x, y, w, cols }) => {
    const rowH = 0.32;
    const headerH = 0.38;
    const totalH = headerH + cols.length * rowH + 0.1;

    s.addShape(pres.shapes.RECTANGLE, { x, y, w, h: totalH,
      fill: { color: WHITE }, line: { color, width: 2 }, shadow: makeShadow() });

    // Header
    s.addShape(pres.shapes.RECTANGLE, { x, y, w, h: headerH,
      fill: { color }, line: { color } });
    s.addText(name, { x, y, w, h: headerH, fontSize: 12, bold: true, color: WHITE,
      align: "center", valign: "middle", margin: 0 });

    // Columns
    cols.forEach((col, i) => {
      const rowY = y + headerH + i * rowH;
      if (i % 2 === 1) {
        s.addShape(pres.shapes.RECTANGLE, { x, y: rowY, w, h: rowH,
          fill: { color: "F0FAF5" }, line: { color: "E0E0E0", width: 0.3 } });
      }
      const isPK = col.startsWith("id");
      const isFK = col.includes("→");
      s.addText(col, { x: x + 0.12, y: rowY, w: w - 0.15, h: rowH, fontSize: 8.5,
        color: isPK ? RED : isFK ? BLUE : SLATE,
        bold: isPK || isFK, align: "left", valign: "middle", margin: 0 });
    });
  });

  // Legend
  s.addText("PK = Primary Key", { x: 0.3, y: 5.1, w: 1.8, h: 0.22, fontSize: 8, color: RED, bold: true, margin: 0 });
  s.addText("FK → Foreign Key", { x: 2.2, y: 5.1, w: 1.8, h: 0.22, fontSize: 8, color: BLUE, bold: true, margin: 0 });
  s.addText("Connection pool: psycopg2  ·  Session pooler (IPv4) via Supabase", {
    x: 4.5, y: 5.1, w: 5.3, h: 0.22, fontSize: 8, color: GREY, align: "right", margin: 0 });
}

// ── Write file ─────────────────────────────────────────────────────────────
const output = "/Users/troy/Documents/AI/Awesist/Awesist_System_Architecture.pptx";
pres.writeFile({ fileName: output }).then(() => console.log("Saved:", output));
