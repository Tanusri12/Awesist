const pptxgen = require("pptxgenjs");
const pres = new pptxgen();
pres.layout = "LAYOUT_16x9";
pres.title = "Awesist Pricing Plans";

// ── Colours ────────────────────────────────────────────────────────────────
const G_DARK  = "075E54";
const G_MED   = "128C7E";
const G_LIGHT = "25D366";
const G_BG    = "DCF8C6";
const WHITE   = "FFFFFF";
const OFF_W   = "F8FFFE";
const SLATE   = "2C3E50";
const LGREY   = "F2F4F7";
const GREY    = "95A5A6";
const DGREY   = "7F8C8D";
const GOLD    = "F39C12";
const PURPLE  = "8E44AD";
const RED     = "E74C3C";
const CHECK   = "25D366";
const CROSS   = "E74C3C";

const makeShadow = () => ({ type: "outer", blur: 10, offset: 4, angle: 135, color: "000000", opacity: 0.10 });
const makeCardShadow = () => ({ type: "outer", blur: 16, offset: 6, angle: 135, color: "000000", opacity: 0.13 });

// ═══════════════════════════════════════════════════════════════════════════
// SLIDE 1 — PRICING CARDS
// ═══════════════════════════════════════════════════════════════════════════
{
  const s = pres.addSlide();
  s.background = { color: "F0F7F5" };

  // ── Top bar ──────────────────────────────────────────────────────────
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 10, h: 0.65, fill: { color: G_DARK }, line: { color: G_DARK } });
  s.addText("Awesist", { x: 0.35, y: 0, w: 2, h: 0.65, fontSize: 18, bold: true, color: G_LIGHT, valign: "middle", margin: 0, fontFace: "Arial Black" });
  s.addText("Simple, Honest Pricing", { x: 2.5, y: 0, w: 5, h: 0.65, fontSize: 15, color: WHITE, valign: "middle", margin: 0 });
  s.addText("30-day free trial on all plans", { x: 7.0, y: 0, w: 2.8, h: 0.65, fontSize: 10, color: G_BG, valign: "middle", align: "right", italic: true, margin: 0 });

  // ── Subtitle ─────────────────────────────────────────────────────────
  s.addText("Choose the plan that fits your business. Cancel anytime.", {
    x: 0, y: 0.72, w: 10, h: 0.3, fontSize: 11, color: DGREY, align: "center", italic: true, margin: 0 });

  // ── Plan cards: 3 columns ─────────────────────────────────────────────
  const plans = [
    {
      name: "Starter",
      price: "299",
      tagline: "Perfect for getting started",
      color: G_MED,
      highlight: false,
      badge: null,
      features: [
        { text: "500 reminders / month", ok: true },
        { text: "Morning summary (daily)", ok: true },
        { text: "Payment & balance tracking", ok: true },
        { text: "Monthly earnings report", ok: true },
        { text: "Customer WhatsApp alerts", ok: false },
        { text: "Priority support", ok: false },
        { text: "Multi-device access", ok: false },
      ],
      cta: "Start Free Trial",
    },
    {
      name: "Pro",
      price: "799",
      tagline: "Most popular for active businesses",
      color: G_DARK,
      highlight: true,
      badge: "MOST POPULAR",
      features: [
        { text: "2,000 reminders / month", ok: true },
        { text: "Morning summary (daily)", ok: true },
        { text: "Payment & balance tracking", ok: true },
        { text: "Monthly earnings report", ok: true },
        { text: "Customer WhatsApp alerts", ok: true },
        { text: "Priority WhatsApp support", ok: true },
        { text: "Multi-device access", ok: false },
      ],
      cta: "Start Free Trial",
    },
    {
      name: "Unlimited",
      price: "1,999",
      tagline: "For power users & large teams",
      color: PURPLE,
      highlight: false,
      badge: null,
      features: [
        { text: "Unlimited reminders", ok: true },
        { text: "Morning summary (daily)", ok: true },
        { text: "Payment & balance tracking", ok: true },
        { text: "Monthly earnings report", ok: true },
        { text: "Customer WhatsApp alerts", ok: true },
        { text: "Dedicated support", ok: true },
        { text: "Multi-device access", ok: true },
      ],
      cta: "Start Free Trial",
    },
  ];

  const cardW = 2.9;
  const cardX = [0.35, 3.55, 6.75];
  const cardY = 1.1;
  const cardH = 4.2;

  plans.forEach((plan, i) => {
    const x = cardX[i];
    const isHighlight = plan.highlight;

    // Card shadow + outer glow for highlighted
    s.addShape(pres.shapes.RECTANGLE, {
      x, y: isHighlight ? cardY - 0.15 : cardY,
      w: cardW, h: isHighlight ? cardH + 0.3 : cardH,
      fill: { color: WHITE },
      line: { color: isHighlight ? plan.color : "E0E0E0", width: isHighlight ? 2.5 : 1 },
      shadow: makeCardShadow(),
    });

    // Colour header band
    s.addShape(pres.shapes.RECTANGLE, {
      x, y: isHighlight ? cardY - 0.15 : cardY,
      w: cardW, h: isHighlight ? 1.35 : 1.2,
      fill: { color: plan.color },
      line: { color: plan.color },
    });

    // Badge
    if (plan.badge) {
      s.addShape(pres.shapes.RECTANGLE, { x: x + 0.7, y: cardY - 0.42, w: 1.5, h: 0.32,
        fill: { color: GOLD }, line: { color: GOLD }, shadow: makeShadow() });
      s.addText(plan.badge, { x: x + 0.7, y: cardY - 0.42, w: 1.5, h: 0.32,
        fontSize: 7.5, bold: true, color: WHITE, align: "center", valign: "middle", margin: 0, charSpacing: 1 });
    }

    const hY = isHighlight ? cardY - 0.15 : cardY;

    // Plan name
    s.addText(plan.name, { x, y: hY + 0.12, w: cardW, h: 0.42,
      fontSize: 18, bold: true, color: WHITE, align: "center", valign: "middle", margin: 0, fontFace: "Arial Black" });

    // Price
    s.addText([
      { text: "₹", options: { fontSize: 14, bold: true, color: WHITE } },
      { text: plan.price, options: { fontSize: 32, bold: true, color: WHITE } },
      { text: "/mo", options: { fontSize: 10, color: isHighlight ? G_BG : "CCEECC" } },
    ], { x, y: hY + 0.52, w: cardW, h: 0.55, align: "center", valign: "middle", margin: 0 });

    // Tagline
    s.addText(plan.tagline, { x: x + 0.1, y: hY + 1.05, w: cardW - 0.2, h: 0.28,
      fontSize: 8, color: isHighlight ? G_BG : "CCEECC", align: "center", italic: true, margin: 0 });

    // Feature rows
    const featY = hY + (isHighlight ? 1.42 : 1.28);
    plan.features.forEach((feat, j) => {
      const fy = featY + j * 0.38;

      // Alternating row bg
      if (j % 2 === 0) {
        s.addShape(pres.shapes.RECTANGLE, { x: x + 0.05, y: fy, w: cardW - 0.1, h: 0.35,
          fill: { color: LGREY }, line: { color: LGREY } });
      }

      // Check or cross circle
      s.addShape(pres.shapes.OVAL, { x: x + 0.15, y: fy + 0.07, w: 0.22, h: 0.22,
        fill: { color: feat.ok ? CHECK : "FFCCCC" }, line: { color: feat.ok ? CHECK : CROSS } });
      s.addText(feat.ok ? "✓" : "✗", { x: x + 0.15, y: fy + 0.07, w: 0.22, h: 0.22,
        fontSize: 8, bold: true, color: feat.ok ? WHITE : CROSS, align: "center", valign: "middle", margin: 0 });

      // Feature text
      s.addText(feat.text, { x: x + 0.42, y: fy + 0.04, w: cardW - 0.52, h: 0.3,
        fontSize: 9, color: feat.ok ? SLATE : DGREY, valign: "middle", margin: 0,
        italic: !feat.ok });
    });

    // CTA button
    const ctaY = hY + cardH - (isHighlight ? 0.0 : 0.15) - 0.55;
    s.addShape(pres.shapes.RECTANGLE, { x: x + 0.3, y: ctaY, w: cardW - 0.6, h: 0.42,
      fill: { color: isHighlight ? G_LIGHT : plan.color },
      line: { color: isHighlight ? G_LIGHT : plan.color },
      shadow: makeShadow() });
    s.addText(plan.cta, { x: x + 0.3, y: ctaY, w: cardW - 0.6, h: 0.42,
      fontSize: 10, bold: true, color: isHighlight ? G_DARK : WHITE,
      align: "center", valign: "middle", margin: 0 });
  });

  // Footer
  s.addText("All plans include a 30-day free trial  ·  No credit card required  ·  Cancel anytime  ·  Prices in INR incl. GST", {
    x: 0, y: 5.42, w: 10, h: 0.2, fontSize: 7.5, color: GREY, align: "center", margin: 0 });
}

// ═══════════════════════════════════════════════════════════════════════════
// SLIDE 2 — FEATURE COMPARISON TABLE
// ═══════════════════════════════════════════════════════════════════════════
{
  const s = pres.addSlide();
  s.background = { color: "F0F7F5" };

  // Top bar
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 10, h: 0.55, fill: { color: G_DARK }, line: { color: G_DARK } });
  s.addText("Awesist", { x: 0.35, y: 0, w: 2, h: 0.55, fontSize: 16, bold: true, color: G_LIGHT, valign: "middle", margin: 0, fontFace: "Arial Black" });
  s.addText("Full Feature Comparison", { x: 2.5, y: 0, w: 7, h: 0.55, fontSize: 14, color: WHITE, valign: "middle", margin: 0 });

  // Column headers
  const cols = [
    { label: "Feature", x: 0.3, w: 3.8, color: SLATE, textColor: WHITE },
    { label: "Starter\n₹299/mo", x: 4.2, w: 1.75, color: G_MED, textColor: WHITE },
    { label: "Pro\n₹799/mo", x: 6.05, w: 1.75, color: G_DARK, textColor: WHITE },
    { label: "Unlimited\n₹1,999/mo", x: 7.9, w: 1.95, color: PURPLE, textColor: WHITE },
  ];

  cols.forEach(({ label, x, w, color, textColor }) => {
    s.addShape(pres.shapes.RECTANGLE, { x, y: 0.65, w, h: 0.52,
      fill: { color }, line: { color } });
    s.addText(label, { x, y: 0.65, w, h: 0.52,
      fontSize: 10, bold: true, color: textColor, align: "center", valign: "middle", margin: 0 });
  });

  // Feature rows
  const rows = [
    { section: true, label: "CORE FEATURES" },
    { label: "Reminders / month", s: "500", p: "2,000", u: "Unlimited" },
    { label: "Order & appointment tracking", s: "✓", p: "✓", u: "✓" },
    { label: "Morning daily summary (8 AM)", s: "✓", p: "✓", u: "✓" },
    { label: "Natural language input (Hinglish)", s: "✓", p: "✓", u: "✓" },
    { label: "Edit & delete reminders", s: "✓", p: "✓", u: "✓" },

    { section: true, label: "PAYMENTS & INCOME" },
    { label: "Payment & balance tracking", s: "✓", p: "✓", u: "✓" },
    { label: "Mark payments as collected", s: "✓", p: "✓", u: "✓" },
    { label: "Monthly earnings report", s: "✓", p: "✓", u: "✓" },
    { label: "Top customer insights", s: "✓", p: "✓", u: "✓" },

    { section: true, label: "CUSTOMER NOTIFICATIONS" },
    { label: "Customer WhatsApp reminders", s: "✗", p: "✓", u: "✓" },
    { label: "Business-type specific messages", s: "✗", p: "✓", u: "✓" },

    { section: true, label: "SUPPORT & ACCESS" },
    { label: "WhatsApp support", s: "Basic", p: "Priority", u: "Dedicated" },
    { label: "Multi-device access", s: "✗", p: "✗", u: "✓" },
    { label: "Data export", s: "✗", p: "✓", u: "✓" },
  ];

  let rowY = 1.25;
  let dataRowIndex = 0;

  rows.forEach((row) => {
    if (row.section) {
      // Section header
      s.addShape(pres.shapes.RECTANGLE, { x: 0.3, y: rowY, w: 9.55, h: 0.28,
        fill: { color: "E8F5E9" }, line: { color: "C8E6C9" } });
      s.addText(row.label, { x: 0.4, y: rowY, w: 9.4, h: 0.28,
        fontSize: 8, bold: true, color: G_MED, valign: "middle", margin: 0, charSpacing: 1 });
      rowY += 0.28;
      return;
    }

    const rowH = 0.32;
    const bg = dataRowIndex % 2 === 0 ? WHITE : LGREY;
    dataRowIndex++;

    // Row bg
    s.addShape(pres.shapes.RECTANGLE, { x: 0.3, y: rowY, w: 9.55, h: rowH,
      fill: { color: bg }, line: { color: "E8E8E8", width: 0.3 } });

    // Feature label
    s.addText(row.label, { x: 0.42, y: rowY, w: 3.68, h: rowH,
      fontSize: 9, color: SLATE, valign: "middle", margin: 0 });

    // Divider
    s.addShape(pres.shapes.LINE, { x: 4.15, y: rowY, w: 0, h: rowH, line: { color: "DDDDDD", width: 0.5 } });

    // Plan values
    [
      { val: row.s, x: 4.2, w: 1.75 },
      { val: row.p, x: 6.05, w: 1.75 },
      { val: row.u, x: 7.9, w: 1.95 },
    ].forEach(({ val, x, w }) => {
      const isCheck = val === "✓";
      const isCross = val === "✗";
      const color = isCheck ? CHECK : isCross ? CROSS : SLATE;
      const bold = isCheck || isCross;
      s.addText(val, { x, y: rowY, w, h: rowH,
        fontSize: isCheck || isCross ? 11 : 8.5,
        color, bold, align: "center", valign: "middle", margin: 0 });
    });

    rowY += rowH;
  });

  // Column borders
  [4.15, 5.95, 7.8].forEach(cx => {
    s.addShape(pres.shapes.LINE, { x: cx, y: 0.65, w: 0, h: rowY - 0.65,
      line: { color: "CCCCCC", width: 0.5 } });
  });

  // "Best value" badge on Pro column
  s.addShape(pres.shapes.RECTANGLE, { x: 6.2, y: rowY + 0.08, w: 1.45, h: 0.28,
    fill: { color: G_LIGHT }, line: { color: G_LIGHT }, shadow: makeShadow() });
  s.addText("BEST VALUE", { x: 6.2, y: rowY + 0.08, w: 1.45, h: 0.28,
    fontSize: 7.5, bold: true, color: G_DARK, align: "center", valign: "middle", margin: 0, charSpacing: 1 });

  // Footer
  s.addText("All plans start with a 30-day free trial  ·  No card required  ·  awesist.duckdns.org", {
    x: 0, y: 5.42, w: 10, h: 0.2, fontSize: 7.5, color: GREY, align: "center", margin: 0 });
}

// ═══════════════════════════════════════════════════════════════════════════
// SLIDE 3 — ROI / WHY PAY SLIDE
// ═══════════════════════════════════════════════════════════════════════════
{
  const s = pres.addSlide();
  s.background = { color: G_DARK };

  // Decorative circles
  s.addShape(pres.shapes.OVAL, { x: 8.2, y: -0.5, w: 3, h: 3, fill: { color: G_MED, transparency: 75 }, line: { color: G_MED, transparency: 75 } });
  s.addShape(pres.shapes.OVAL, { x: -0.5, y: 3.5, w: 2.5, h: 2.5, fill: { color: G_LIGHT, transparency: 80 }, line: { color: G_LIGHT, transparency: 80 } });

  // Header
  s.addText("Is it worth it?", { x: 0.5, y: 0.3, w: 9, h: 0.65,
    fontSize: 32, bold: true, color: WHITE, fontFace: "Arial Black", margin: 0 });
  s.addText("Here's what Awesist saves you vs. the cost", { x: 0.5, y: 0.95, w: 9, h: 0.35,
    fontSize: 13, color: G_BG, italic: true, margin: 0 });

  // Stat cards
  const stats = [
    { top: "₹12,500", mid: "avg monthly collections", bot: "per vendor on trial", color: G_LIGHT, textColor: G_DARK },
    { top: "₹799", mid: "Pro plan cost", bot: "= 6.4% of collections", color: WHITE, textColor: G_DARK },
    { top: "3–5 hrs", mid: "saved per week", bot: "no manual tracking", color: GOLD, textColor: G_DARK },
    { top: "₹0", mid: "missed payments", bot: "with reminders on", color: G_LIGHT, textColor: G_DARK },
  ];

  stats.forEach(({ top, mid, bot, color, textColor }, i) => {
    const x = 0.5 + i * 2.28;
    s.addShape(pres.shapes.RECTANGLE, { x, y: 1.45, w: 2.1, h: 1.5,
      fill: { color }, line: { color }, shadow: makeCardShadow() });
    s.addText(top, { x, y: 1.52, w: 2.1, h: 0.6,
      fontSize: 28, bold: true, color: textColor, align: "center", valign: "middle", margin: 0, fontFace: "Arial Black" });
    s.addText(mid, { x, y: 2.1, w: 2.1, h: 0.35,
      fontSize: 8.5, bold: true, color: textColor, align: "center", valign: "middle", margin: 0 });
    s.addText(bot, { x, y: 2.44, w: 2.1, h: 0.3,
      fontSize: 8, color: textColor, align: "center", valign: "middle", italic: true, margin: 0 });
  });

  // Comparison row
  s.addShape(pres.shapes.RECTANGLE, { x: 0.5, y: 3.15, w: 9.1, h: 0.04,
    fill: { color: G_MED, transparency: 50 }, line: { color: G_MED, transparency: 50 } });

  const compItems = [
    { label: "Missed order reminder", cost: "Lost ₹500–2,000" },
    { label: "Manual notepad tracking", cost: "2 hrs/day wasted" },
    { label: "Forgotten customer follow-up", cost: "Lost repeat business" },
    { label: "Awesist Pro", cost: "₹26/day" },
  ];

  compItems.forEach(({ label, cost }, i) => {
    const x = 0.5 + i * 2.28;
    const isAwesist = i === 3;
    s.addShape(pres.shapes.RECTANGLE, { x, y: 3.3, w: 2.1, h: 0.85,
      fill: { color: isAwesist ? G_LIGHT : "1A3A35" },
      line: { color: isAwesist ? G_LIGHT : G_MED, width: isAwesist ? 2 : 1 },
      shadow: makeShadow() });
    s.addText(label, { x, y: 3.33, w: 2.1, h: 0.4,
      fontSize: 8.5, bold: true, color: isAwesist ? G_DARK : WHITE,
      align: "center", valign: "middle", margin: 2 });
    s.addText(cost, { x, y: 3.72, w: 2.1, h: 0.35,
      fontSize: isAwesist ? 10 : 9, bold: true,
      color: isAwesist ? G_DARK : RED,
      align: "center", valign: "middle", margin: 0 });
  });

  // CTA
  s.addText("Start your 30-day free trial — no card needed.", { x: 0.5, y: 4.35, w: 9.1, h: 0.4,
    fontSize: 14, bold: true, color: G_LIGHT, align: "center", margin: 0 });
  s.addText("Just send a WhatsApp message to get started.", { x: 0.5, y: 4.72, w: 9.1, h: 0.3,
    fontSize: 11, color: G_BG, align: "center", italic: true, margin: 0 });

  // Bottom tagline
  s.addText("Less than a cup of chai a day. 🍵", { x: 0.5, y: 5.22, w: 9.1, h: 0.3,
    fontSize: 10, color: GREY, align: "center", italic: true, margin: 0 });
}

// ── Write ──────────────────────────────────────────────────────────────────
const output = "/Users/troy/Documents/AI/Awesist/Awesist_Pricing.pptx";
pres.writeFile({ fileName: output }).then(() => console.log("Saved:", output));
