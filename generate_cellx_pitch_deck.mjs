import fs from "node:fs/promises";
import path from "node:path";
import { Presentation, PresentationFile } from "@oai/artifact-tool";

const OUT = "outputs/business_plan_20260831";
const PPTX = path.join(OUT, "CellX_RDP_Competition_Pitch_Deck_20_Slides_Investor_Case_AI_Comps_Presenters_Header_Link.pptx");
const LOGO = path.resolve("rdp-marketing-site/assets/logo.png");
const VIS = path.resolve("outputs/business_plan_20260831/visuals");
const CELLX_LOGO_SVG = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 180 72">
  <rect width="180" height="72" fill="none"/>
  <path d="M18 36 L42 12 L82 52 L58 72 Z" fill="#3F66B5"/>
  <path d="M42 60 L82 20 L58 0 L18 40 Z" fill="#3F66B5" opacity="0.95"/>
  <path d="M88 16 L116 0 H164 V24 H120 L100 44 Z" fill="#10B8D9"/>
  <path d="M88 56 L116 72 H164 V48 H120 L100 28 Z" fill="#10B8D9"/>
  <path d="M132 36 L156 12 L180 36 L156 60 Z" fill="#3F66B5"/>
</svg>`;

const C = {
  navy: "#14213D",
  blue: "#1F6FEB",
  cyan: "#10B8D9",
  green: "#16A34A",
  orange: "#F59E0B",
  purple: "#7C3AED",
  ink: "#111827",
  muted: "#526276",
  pale: "#EEF6FF",
  line: "#C7D8F2",
  white: "#FFFFFF",
};

async function writeBlob(filePath, blob) {
  await fs.writeFile(filePath, new Uint8Array(await blob.arrayBuffer()));
}

function tb(slide, text, x, y, w, h, style = {}) {
  const shape = slide.shapes.add({
    geometry: "textbox",
    position: { left: x, top: y, width: w, height: h },
    fill: "none",
    line: { style: "solid", fill: "none", width: 0 },
  });
  shape.text = text;
  shape.text.style = {
    fontSize: style.fontSize ?? 24,
    bold: style.bold ?? false,
    color: style.color ?? C.ink,
    alignment: style.alignment,
  };
  return shape;
}

function box(slide, x, y, w, h, fill = C.white, line = C.line, radius = "rounded-lg") {
  return slide.shapes.add({
    geometry: "roundRect",
    position: { left: x, top: y, width: w, height: h },
    fill,
    line: { style: "solid", fill: line, width: 1 },
    borderRadius: radius,
    shadow: "shadow-sm",
  });
}

function title(slide, t, sub = "") {
  slide.background.fill = "#F3F8FF";
  const brand = tb(slide, "Cell AI Data", 54, 34, 180, 28, { fontSize: 15, bold: true, color: C.blue });
  brand.text.get("Cell AI Data").link = { uri: "https://cellaidata.com", isExternal: true };
  const longTitle = t.length > 46;
  tb(slide, t, 54, 78, 820, longTitle ? 108 : 86, { fontSize: longTitle ? 31 : 36, bold: true, color: C.navy });
  if (sub) tb(slide, sub, 56, longTitle ? 176 : 152, 920, 50, { fontSize: 16, color: C.muted });
  slide.images.add({ svg: CELLX_LOGO_SVG, alt: "CellX logo", fit: "contain", position: { left: 1068, top: 24, width: 140, height: 56 } });
}

function bulletList(slide, items, x, y, w, gap = 44) {
  items.forEach((item, i) => {
    const yy = y + i * gap;
    slide.shapes.add({ geometry: "ellipse", position: { left: x, top: yy + 8, width: 10, height: 10 }, fill: C.blue, line: { style: "solid", fill: C.blue, width: 0 } });
    tb(slide, item, x + 24, yy, w, 34, { fontSize: 18, color: C.ink });
  });
}

function stat(slide, label, value, x, y, w, color = C.blue) {
  box(slide, x, y, w, 110, C.white, C.line);
  tb(slide, value, x + 22, y + 20, w - 44, 42, { fontSize: value.length > 16 ? 24 : 30, bold: true, color });
  tb(slide, label, x + 22, y + 65, w - 44, 28, { fontSize: 13, color: C.muted });
}

function workflowNode(slide, label, type, x, y, color, subtitle = "") {
  box(slide, x, y, 190, 84, C.white, "#AFC8EE");
  slide.shapes.add({ geometry: "rect", position: { left: x, top: y, width: 190, height: 24 }, fill: color, line: { style: "solid", fill: color, width: 0 } });
  tb(slide, type.toUpperCase(), x + 12, y + 4, 156, 16, { fontSize: 10, bold: true, color: C.white });
  tb(slide, label, x + 12, y + 34, 166, 24, { fontSize: 15, bold: true, color: C.ink });
  if (subtitle) tb(slide, subtitle, x + 12, y + 58, 166, 18, { fontSize: 10.5, color: C.muted });
}

function arrow(slide, x1, y1, x2, y2) {
  const left = Math.min(x1, x2);
  const top = Math.min(y1, y2) - 6;
  const width = Math.max(20, Math.abs(x2 - x1));
  const height = Math.max(12, Math.abs(y2 - y1) + 12);
  slide.shapes.add({
    geometry: "rightArrow",
    position: { left, top, width, height },
    fill: "#6B7C93",
    line: { style: "solid", fill: "#6B7C93", width: 0 },
  });
}

function iconBadge(slide, x, y, color, label) {
  slide.shapes.add({ geometry: "ellipse", position: { left: x, top: y, width: 46, height: 46 }, fill: color, line: { style: "solid", fill: color, width: 0 } });
  tb(slide, label, x, y + 11, 46, 22, { fontSize: label.length > 2 ? 13 : 18, bold: true, color: C.white, alignment: "center" });
}

function metricPill(slide, x, y, label, value, color) {
  box(slide, x, y, 250, 92, C.white, "#BFD3F3");
  tb(slide, value, x + 22, y + 16, 205, 30, { fontSize: 27, bold: true, color });
  tb(slide, label, x + 22, y + 54, 205, 24, { fontSize: 16, color: C.muted });
}

function drawBigIdeaStrip(slide, x, y) {
  const ideas = [
    ["Software-defined software", "Business apps become metadata, workflow, and policy."],
    ["One-person AI company", "Small teams coordinate research, data, and follow-up."],
    ["Cost down, output up", "Automate repetitive work with human approval where needed."],
  ];
  ideas.forEach((idea, i) => {
    const xx = x + i * 342;
    box(slide, xx, y, 316, 88, i === 1 ? "#EEF2FF" : C.white, i === 1 ? "#C4B5FD" : "#BFD3F3");
    iconBadge(slide, xx + 18, y + 22, [C.blue, C.purple, C.green][i], ["SD", "AI", "ROI"][i]);
    tb(slide, idea[0], xx + 76, y + 16, 220, 24, { fontSize: 16, bold: true, color: C.navy });
    tb(slide, idea[1], xx + 76, y + 46, 214, 30, { fontSize: 11, color: C.muted });
  });
}

function drawPainVisual(s) {
  [["Every team", "Needs custom tools", C.orange], ["Legacy core", "Risky to modify", C.navy], ["AI pilots", "Outside workflow", C.purple]].forEach((c, i) => {
    const x = 92 + i * 360;
    box(s, x, 270, 300, 210, C.white, "#C7D8F2");
    iconBadge(s, x + 24, 298, c[2], String(i + 1));
    tb(s, c[0], x + 88, 295, 170, 32, { fontSize: 26, bold: true, color: C.navy });
    tb(s, c[1], x + 88, 337, 170, 28, { fontSize: 18, color: C.muted });
    tb(s, ["Marketing, sales, ops, support all change fast", "Developers must protect stability", "Agent work needs data, tools, cost control"][i], x + 30, 400, 238, 54, { fontSize: 18, color: C.ink });
  });
  tb(s, "CellX converts business logic into governed reusable workflows.", 155, 540, 960, 42, { fontSize: 29, bold: true, color: C.blue, alignment: "center" });
  tb(s, "AI-era demand: companies want software that can be redefined as fast as the business changes.", 205, 590, 860, 28, { fontSize: 18, color: C.muted, alignment: "center" });
}

function drawProductMockup(s) {
  box(s, 84, 236, 520, 330, C.white, "#BFD3F3");
  s.shapes.add({ geometry: "rect", position: { left: 84, top: 236, width: 520, height: 48 }, fill: C.navy, line: { style: "solid", fill: C.navy, width: 0 } });
  tb(s, "Generated Business Console", 112, 248, 330, 24, { fontSize: 20, bold: true, color: C.white });
  [["Module", "Data", "Workflow", "Status"], ["Marketing", "Campaigns", "Video + social", "Live"], ["Supply Chain", "SKUs", "Vendor + stock", "Live"]].forEach((row, r) => {
    row.forEach((txt, c) => {
      const x = 112 + c * 112, y = 318 + r * 52;
      if (r === 0) tb(s, txt, x, y, 95, 20, { fontSize: 16, bold: true, color: C.navy });
      else tb(s, txt, x, y, 96, 20, { fontSize: 16, color: C.ink });
    });
  });
  [["Configure", "Database fields"], ["Generate", "Pages + forms"], ["Secure", "Roles + actions"], ["Extend", "Workflow hooks"]].forEach((c, i) => {
    const x = 690, y = 242 + i * 78;
    iconBadge(s, x, y, [C.blue, C.cyan, C.green, C.purple][i], ["C", "G", "S", "E"][i]);
    tb(s, c[0], x + 66, y + 2, 260, 26, { fontSize: 24, bold: true, color: C.navy });
    tb(s, c[1], x + 66, y + 36, 300, 24, { fontSize: 17, color: C.muted });
  });
  tb(s, "Software-defined software", 96, 582, 300, 28, { fontSize: 24, bold: true, color: C.blue });
  tb(s, "Instead of rewriting modules, users redefine pages, workflows, permissions, and AI skills as configuration.", 405, 586, 700, 24, { fontSize: 16, color: C.muted });
}

function drawNodeLibrary(s) {
  const cats = [
    ["Marketing", "TikTok / FB / influencers", C.orange],
    ["Sales", "CRM / quotes / follow-up", C.blue],
    ["Commerce", "Amazon / Shopify / listings", C.navy],
    ["Operations", "Tasks / approvals / alerts", "#64748B"],
    ["Shipping", "FedEx / UPS / DHL", "#0891B2"],
    ["Finance", "Stripe / PayPal / invoices", C.green],
    ["AI Models", "OpenAI / Claude / Gemini", C.purple],
    ["CellX DB", "Query / CRUD / Excel", "#0F766E"],
  ];
  cats.forEach((c, i) => {
    const x = 80 + (i % 4) * 288, y = 230 + Math.floor(i / 4) * 148;
    box(s, x, y, 244, 112, C.white, "#BFD3F3");
    iconBadge(s, x + 18, y + 28, c[2], c[0][0]);
    tb(s, c[0], x + 78, y + 26, 138, 26, { fontSize: 22, bold: true, color: C.navy });
    tb(s, c[1], x + 78, y + 62, 140, 32, { fontSize: 16, color: C.muted });
  });
}

function drawDbActivation(s) {
  box(s, 84, 258, 332, 250, C.white, "#BFD3F3");
  tb(s, "CellX Tables", 118, 292, 230, 28, { fontSize: 26, bold: true, color: C.navy });
  ["cx_order", "gen_table", "gen_table_column", "cx_workflow_log"].forEach((t, i) => tb(s, t, 125, 346 + i * 38, 220, 22, { fontSize: 18, color: C.ink }));
  arrow(s, 416, 382, 535, 382);
  box(s, 550, 258, 292, 250, "#F0FDF4", "#86EFAC");
  tb(s, "Safe Workflow Nodes", 590, 292, 230, 28, { fontSize: 25, bold: true, color: C.green });
  ["Query", "Create / Update", "Export Excel", "Audit Log"].forEach((t, i) => tb(s, t, 612, 346 + i * 38, 200, 22, { fontSize: 18, color: C.ink }));
  arrow(s, 842, 382, 965, 382);
  box(s, 980, 258, 220, 250, "#EEF2FF", "#C4B5FD");
  tb(s, "Business Value", 1015, 292, 160, 28, { fontSize: 24, bold: true, color: C.purple });
  tb(s, "Existing backend data becomes usable in AI workflows without rebuilding the core.", 1012, 350, 150, 100, { fontSize: 18, color: C.ink });
}

function drawAiModes(s) {
  [["Platform API", "Managed by CellX\nBest for automation", C.blue], ["Bring Your Own Key", "Customer pays model bill\nBest for teams", C.green], ["ChatGPT Handoff", "Manual copy/paste\nNo platform token burn", C.purple]].forEach((c, i) => {
    const x = 115 + i * 360;
    box(s, x, 255, 300, 250, C.white, "#BFD3F3");
    iconBadge(s, x + 122, 288, c[2], ["API", "KEY", "WEB"][i]);
    tb(s, c[0], x + 28, 362, 244, 32, { fontSize: 25, bold: true, color: C.navy, alignment: "center" });
    tb(s, c[1], x + 38, 418, 224, 58, { fontSize: 18, color: C.muted, alignment: "center" });
  });
  tb(s, "Designed for lean AI-era teams: automate safe work, bring customer-owned keys when needed, and use manual ChatGPT handoff when token cost must stay outside CellX.", 118, 548, 1040, 58, { fontSize: 20, bold: true, color: C.navy, alignment: "center" });
}

function drawCustomers(s) {
  [["Retail & Brands", "Promotion, sales,\norders, support", C.blue], ["Manufacturing", "Inventory, suppliers,\nquality, approvals", C.cyan], ["Education", "Enrollment, classes,\nnotices, reports", C.green], ["Agencies", "Client portals,\nrepeatable delivery", C.orange]].forEach((c, i) => {
    const x = 92 + i * 286;
    box(s, x, 265, 236, 230, C.white, "#BFD3F3");
    iconBadge(s, x + 28, 304, c[2], c[0][0]);
    tb(s, c[0], x + 28, 370, 180, 28, { fontSize: 25, bold: true, color: C.navy });
    tb(s, c[1], x + 28, 420, 180, 56, { fontSize: 18, color: C.muted });
  });
}

function drawBusinessLifecycle(s) {
  const steps = [
    ["Promote", "AI videos, ads, influencer outreach", C.orange],
    ["Sell", "Leads, quotes, CRM, follow-up", C.blue],
    ["Fulfill", "Orders, inventory, suppliers, shipping", C.green],
    ["Support", "Tickets, returns, knowledge base", C.purple],
    ["Analyze", "Excel, dashboards, finance, decisions", "#0F766E"],
  ];
  steps.forEach((step, i) => {
    const x = 72 + i * 232;
    box(s, x, 282, 190, 168, C.white, "#BFD3F3");
    iconBadge(s, x + 72, 306, step[2], String(i + 1));
    tb(s, step[0], x + 16, 365, 158, 24, { fontSize: 22, bold: true, color: C.navy, alignment: "center" });
    tb(s, step[1], x + 18, 402, 154, 40, { fontSize: 12, color: C.muted, alignment: "center" });
    if (i < steps.length - 1) arrow(s, x + 190, 354, x + 230, 354);
  });
  tb(s, "One operator can launch and supervise an end-to-end company workflow.", 160, 535, 960, 34, { fontSize: 27, bold: true, color: C.blue, alignment: "center" });
}

function drawMarketingAutomation(s) {
  const xs = [58, 250, 442, 634, 826, 1018];
  [["Trend Search", "Research", C.navy], ["Video Script", "AI", C.purple], ["Ad Creative", "Media", C.orange], ["Influencer List", "Social", C.blue], ["Post to TK/FB", "Channel", C.cyan], ["Lead Capture", "Sales", C.green]].forEach((n, i) => {
    workflowNode(s, n[0], n[1], xs[i], 326, n[2], i === 4 ? "TikTok / Facebook / social" : "");
    if (i < 5) arrow(s, xs[i] + 190, 368, xs[i + 1] - 2, 368);
  });
  tb(s, "Marketing is the first showcase: product promotion, video generation, influencer outreach, social distribution, and lead handoff.", 80, 505, 1080, 46, { fontSize: 20, bold: true, color: C.navy, alignment: "center" });
}

function drawCompetition(s) {
  const rows = [
    ["PLTR", "Operational AI + data platform", "$4.48B 2025, +56%", "+492%"],
    ["CRM", "Agentforce + Data Cloud", "$41.5B FY26, +10%", "+3%"],
    ["NOW", "Enterprise AI workflows", "$13.28B 2025, +21%", "-15%"],
    ["PATH", "RPA + agentic automation", "$1.61B FY26, +13%", "+41%"],
    ["AI", "Enterprise AI apps", "$250M FY26, -36%", "-55%"],
    ["MSFT", "Copilot + Power Platform", "$331.8B FY26, +18%", "+25%"],
  ];
  s.shapes.add({ geometry: "rect", position: { left: 70, top: 226, width: 1120, height: 42 }, fill: C.navy, line: { style: "solid", fill: C.navy, width: 0 } });
  ["Ticker", "AI workflow angle", "Latest revenue signal", "2-year stock"].forEach((h, i) => tb(s, h, [92, 220, 560, 930][i], 238, [80, 270, 300, 180][i], 20, { fontSize: 15, bold: true, color: C.white, alignment: i === 3 ? "center" : undefined }));
  rows.forEach((row, r) => {
    const y = 282 + r * 48;
    box(s, 70, y, 1120, 36, row[0] === "PLTR" ? "#E8FFF3" : row[0] === "AI" ? "#FFF7ED" : C.white, row[0] === "PLTR" ? "#86EFAC" : row[0] === "AI" ? "#FDBA74" : C.line);
    tb(s, row[0], 96, y + 8, 70, 18, { fontSize: 16, bold: true, color: row[0] === "PLTR" ? C.green : C.navy });
    tb(s, row[1], 220, y + 8, 290, 18, { fontSize: 14, bold: true, color: C.ink });
    tb(s, row[2], 560, y + 8, 300, 18, { fontSize: 14, color: C.muted });
    tb(s, row[3], 940, y + 8, 110, 18, { fontSize: 15, bold: true, color: row[3].startsWith("-") ? "#DC2626" : C.green, alignment: "center" });
  });
  tb(s, "Investor signal: the market rewards AI tied to data, workflows, and execution. It punishes AI stories without durable growth.", 120, 596, 1040, 38, { fontSize: 20, bold: true, color: C.blue, alignment: "center" });
}

function drawCompetitorDeepDive(s) {
  const rows = [
    ["Palantir AIP", "Data + ontology + AI decisions", "CellX is lighter, SMB-friendly, and workflow-template driven."],
    ["Salesforce Agentforce", "CRM agents inside a huge app suite", "CellX starts outside CRM: operations, data apps, and private deployments."],
    ["ServiceNow AI", "Enterprise workflow system of record", "CellX can sell smaller teams that cannot buy large enterprise platforms."],
    ["UiPath agents", "Automation and RPA execution", "CellX begins with generated apps plus database workflow, not bot-only automation."],
    ["C3.ai", "Enterprise AI applications", "C3.ai shows investors need growth proof, not only AI positioning."],
  ];
  s.shapes.add({ geometry: "rect", position: { left: 74, top: 230, width: 1128, height: 42 }, fill: C.navy, line: { style: "solid", fill: C.navy, width: 0 } });
  ["Competitor", "Primary strength", "CellX opening"].forEach((h, i) => tb(s, h, [96, 370, 650][i], 241, [220, 230, 480][i], 20, { fontSize: 16, bold: true, color: C.white }));
  rows.forEach((row, r) => {
    const y = 286 + r * 58;
    box(s, 74, y, 1128, 44, r === 0 ? "#E8FFF3" : C.white, r === 0 ? "#86EFAC" : C.line);
    tb(s, row[0], 96, y + 11, 235, 20, { fontSize: 15, bold: true, color: C.navy });
    tb(s, row[1], 370, y + 11, 230, 20, { fontSize: 15, bold: true, color: C.ink });
    tb(s, row[2], 650, y + 9, 480, 24, { fontSize: 14, color: C.muted });
  });
  tb(s, "CellX should not pitch as another chatbot. It should pitch as AI workflow infrastructure for lean business operations.", 118, 600, 1040, 38, { fontSize: 20, bold: true, color: C.blue, alignment: "center" });
}

function drawSwot(s) {
  const quadrants = [
    ["Strengths", "Working prototype\nBackend-adjacent data model\nAI modes protect token cost", C.green, "#F0FDF4"],
    ["Weaknesses", "Early brand awareness\nConnector depth still maturing\nFounder-led delivery load", C.orange, "#FFF7ED"],
    ["Opportunities", "Low-code + agentic AI growth\nSMB automation demand\nTemplate marketplace leverage", C.blue, "#EFF6FF"],
    ["Threats", "Large platform bundling\nSecurity expectations\nCrowded automation market", C.purple, "#F5F3FF"],
  ];
  quadrants.forEach((q, i) => {
    const x = 86 + (i % 2) * 560;
    const y = 236 + Math.floor(i / 2) * 176;
    box(s, x, y, 500, 136, q[4], q[3]);
    iconBadge(s, x + 24, y + 28, q[3], q[0][0]);
    tb(s, q[0], x + 88, y + 26, 300, 28, { fontSize: 25, bold: true, color: C.navy });
    tb(s, q[1], x + 90, y + 66, 360, 56, { fontSize: 16, color: C.ink });
  });
  tb(s, "The strategy is to turn current strengths into investor proof: paid pilots, repeatable templates, and visible customer ROI.", 130, 595, 1020, 38, { fontSize: 20, bold: true, color: C.navy, alignment: "center" });
}

function drawGtm(s) {
  [["Demo", "Website + workflow story", C.blue], ["Pilot", "E-commerce ops teams", C.cyan], ["Templates", "Amazon, carriers, payments", C.purple], ["Partners", "Agencies + integrators", C.green]].forEach((c, i) => {
    const w = 870 - i * 120, x = 205 + i * 60, y = 245 + i * 82;
    s.shapes.add({ geometry: "trapezoid", position: { left: x, top: y, width: w, height: 62 }, fill: c[2], line: { style: "solid", fill: c[2], width: 0 } });
    tb(s, c[0], x + 30, y + 15, 150, 24, { fontSize: 23, bold: true, color: C.white });
    tb(s, c[1], x + 225, y + 17, 420, 22, { fontSize: 18, color: C.white });
  });
  tb(s, "Wedge message: turn one operator into an AI-augmented team by packaging repeatable business workflows.", 150, 590, 980, 34, { fontSize: 21, bold: true, color: C.navy, alignment: "center" });
}

function drawGtmEngine(s) {
  const rows = [
    ["Beachhead", "E-commerce, agencies, SMB ops", "Pain is visible and demos are concrete"],
    ["Motion", "Founder-led pilots + public demos", "Convert workflow templates into paid proof"],
    ["Channels", "Content, partners, marketplaces", "Lower CAC after the first case studies"],
    ["Expansion", "More workflows, seats, connectors", "Grow from one use case into operations"],
  ];
  rows.forEach((row, i) => {
    const y = 238 + i * 82;
    box(s, 82, y, 1088, 58, i === 0 ? "#E8FFF3" : C.white, i === 0 ? "#86EFAC" : C.line);
    tb(s, row[0], 112, y + 15, 160, 24, { fontSize: 18, bold: true, color: i === 0 ? C.green : C.navy });
    tb(s, row[1], 300, y + 15, 350, 24, { fontSize: 17, bold: true, color: C.ink });
    tb(s, row[2], 690, y + 15, 420, 24, { fontSize: 16, color: C.muted });
  });
  tb(s, "The practical launch path is narrow first, then repeatable: prove one-person company workflows, package templates, and let partners resell implementation.", 105, 590, 1020, 42, { fontSize: 20, bold: true, color: C.navy, alignment: "center" });
}

function drawPricingLadder(s) {
  const tiers = [["Trial", "$0", "Demo entry"], ["Starter", "$99/mo", "SMB launch"], ["Growth", "$299/mo", "Workflow scale"], ["Enterprise", "$899+/mo", "Private deployment"]];
  tiers.forEach((r, i) => {
    const x = 70 + i * 292;
    box(s, x, 270 - i * 18, 250, 190 + i * 18, C.white, "#BFD3F3");
    tb(s, r[0], x + 28, 300 - i * 18, 190, 28, { fontSize: 24, bold: true, color: C.navy });
    tb(s, r[1], x + 28, 348 - i * 18, 190, 38, { fontSize: 31, bold: true, color: i === 0 ? C.green : C.blue });
    tb(s, r[2], x + 28, 410 - i * 18, 190, 28, { fontSize: 18, color: C.muted });
  });
  arrow(s, 320, 370, 360, 360); arrow(s, 612, 350, 652, 340); arrow(s, 904, 330, 944, 320);
  tb(s, "Land with generated pages. Expand with workflows, integrations, and private deployments.", 130, 550, 1020, 40, { fontSize: 25, bold: true, color: C.navy, alignment: "center" });
}

function drawRevenueModel(s) {
  const streams = [
    ["Subscription", "$99-$899+/mo", "Recurring SaaS and private deployment fees", C.blue],
    ["Implementation", "$2k-$15k", "Workflow setup, data mapping, connector rollout", C.green],
    ["Templates", "$29-$499", "Industry packs and premium agent nodes", C.purple],
    ["Usage", "Pass-through", "AI tokens, storage, advanced connectors", C.orange],
  ];
  streams.forEach((stream, i) => {
    const x = 70 + i * 292;
    box(s, x, 252, 250, 230, i === 1 ? "#F0FDF4" : C.white, i === 1 ? "#86EFAC" : "#BFD3F3");
    iconBadge(s, x + 28, 282, stream[3], String(i + 1));
    tb(s, stream[0], x + 28, 350, 190, 28, { fontSize: 23, bold: true, color: C.navy });
    tb(s, stream[1], x + 28, 395, 190, 32, { fontSize: 25, bold: true, color: stream[3] });
    tb(s, stream[2], x + 28, 440, 190, 42, { fontSize: 13, color: C.muted });
  });
  tb(s, "Early revenue comes from paid pilots and setup. Scalable margin comes from subscriptions, templates, and repeatable partner delivery.", 120, 550, 1040, 42, { fontSize: 22, bold: true, color: C.navy, alignment: "center" });
}

function drawFinancialOutlook(s) {
  const cols = [96, 292, 500, 708, 916];
  const headers = ["Investor case", "Year 1", "Year 2", "Year 3", "Signal"];
  s.shapes.add({ geometry: "rect", position: { left: 78, top: 226, width: 1080, height: 42 }, fill: C.navy, line: { style: "solid", fill: C.navy, width: 0 } });
  headers.forEach((h, i) => tb(s, h, cols[i], 236, i === 0 ? 160 : 150, 22, { fontSize: 16, bold: true, color: C.white, alignment: "center" }));
  const rows = [
    ["Ending paid accounts", "35", "220", "900", "Narrow wedge then partners"],
    ["ARR run-rate", "$180k", "$1.25M", "$6.0M", "Growth + Enterprise mix"],
    ["Recognized revenue", "$250k", "$1.2M", "$4.8M", "SaaS + setup + templates"],
    ["Gross margin", "68%", "76%", "84%", "BYOK and templates lift margin"],
    ["Operating profit", "-$260k", "-$90k", "$1.25M", "Scale leverage in Year 3"],
  ];
  rows.forEach((row, r) => {
    const y = 282 + r * 56;
    box(s, 78, y, 1080, 44, r === 4 ? "#E8FFF3" : C.white, r === 4 ? "#86EFAC" : C.line);
    row.forEach((txt, c) => tb(s, txt, cols[c], y + 11, c === 0 ? 160 : c === 4 ? 210 : 120, 20, { fontSize: c === 0 ? 14 : 16, bold: c > 0 && c < 4, color: c === 4 ? C.muted : C.ink, alignment: c > 0 && c < 4 ? "center" : undefined }));
  });
  tb(s, "Investor case, not audited forecasts: upside comes from repeatable templates, partner delivery, and expansion from one workflow into operations.", 135, 598, 1010, 36, { fontSize: 18, bold: true, color: C.blue, alignment: "center" });
}

function drawAsk(s) {
  tb(s, "Presented by", 84, 266, 220, 26, { fontSize: 20, bold: true, color: C.blue });
  tb(s, "Harrison Huang\nDavid Cai", 84, 310, 520, 92, { fontSize: 34, bold: true, color: C.ink });
  tb(s, "Tarbut V' Torah (TVT) Community Day School\n9th Grade", 84, 436, 620, 58, { fontSize: 22, color: C.muted });
  box(s, 760, 276, 350, 238, "#E8FFF3", "#86EFAC");
  tb(s, "Competition ask", 798, 308, 270, 30, { fontSize: 26, bold: true, color: C.green });
  bulletList(s, ["Pilot customer introductions", "Cloud credits for production tests", "AI governance mentorship"], 802, 360, 260, 50);
}

const slides = [
  {
    t: "CellX RDP",
    sub: "Software-defined business platform for the one-person AI company era",
    kind: "cover",
  },
  {
    t: "Every business team now needs its own software logic",
    sub: "Marketing, sales, operations, supply chain, support, finance, and admin teams all need custom workflows faster than traditional development can deliver.",
    layout: "pain",
    bullets: ["Business processes change faster than software release cycles.", "Low-code tools often miss real database and permission context.", "AI experiments sit outside the workflow and create cost and governance concerns."],
  },
  {
    t: "CellX turns business logic into configurable software",
    sub: "Business logic becomes configurable metadata, workflow, permissions, and AI skills.",
    layout: "product",
    cards: [["Configure", "Tables, fields, search forms, validation"], ["Generate", "Admin pages, menus, roles, actions"], ["Extend", "Custom pages, LiteFlow-style hooks, sidecar APIs"], ["Operate", "Deploy on Lightsail with app.cellaidata.com"]],
  },
  {
    t: "A working platform prototype, not just a pitch",
    sub: "The current project already has a public site, a deployed backend, and a workflow designer extension for cross-industry processes.",
    visual: "cellx_architecture.png",
    cards: [["cellaidata.com", "Marketing, pricing, trial/demo, AI workflow promotion"], ["app.cellaidata.com", "CellX backend with admin and order data"], ["/workflow/", "Visual workflow skill designer"], ["/ext-api", "Extension API concept for integrations"]],
  },
  {
    t: "From promotion to support: one configurable workflow layer",
    sub: "CellX is not limited to order management. Orders are one node in a larger business operating system.",
    layout: "lifecycle",
  },
  {
    t: "Node Library covers the full company stack",
    sub: "Users browse categories and drag reusable skills for marketing, sales, commerce, operations, support, data, and AI.",
    layout: "library",
    cards: [["Marketing", "TikTok, Facebook, video ads, influencer outreach"], ["Sales", "CRM, lead scoring, quotes, follow-up"], ["Commerce", "Amazon, Shopify, product listings"], ["Operations", "Approvals, tasks, alerts, SOPs"], ["Supply Chain", "Inventory, suppliers, shipping, procurement"], ["Support", "Tickets, returns, knowledge base, email"], ["AI Models", "OpenAI, Claude, Gemini, DeepSeek, Mistral, Llama"], ["CellX DB", "Query, create, update, delete, export Excel"]],
  },
  {
    t: "CellX Database nodes activate every business table",
    sub: "Workflow should not be separate from company data. It should safely use marketing, sales, inventory, order, finance, and support tables.",
    layout: "db",
    bullets: ["Allow-listed table access for query, create, update, delete, and export.", "Parameterized queries, audit logs, permissions, and approval gates.", "Works even when the original backend JAR source is unavailable."],
  },
  {
    t: "AI cost strategy: three modes",
    sub: "Customers can choose automation level and token ownership per AI node.",
    layout: "aiModes",
    cards: [["Platform API", "CellX manages AI keys and bills usage."], ["Bring Your Own Key", "Customer enters their OpenAI/Claude/Gemini key."], ["Manual Web Handoff", "User logs into ChatGPT, copies prompt/result, no platform token burn."]],
  },
  {
    t: "Example: AI marketing automation for a one-person company",
    sub: "Generate product promotion content, identify influencers, distribute to TikTok/Facebook, capture leads, and hand off to sales.",
    marketingFlow: true,
  },
  {
    t: "Industry coverage",
    sub: "The same platform pattern applies across verticals because the core product is configurable business logic.",
    layout: "customers",
    cards: [["Retail & Brands", "Marketing, orders, loyalty, support"], ["Manufacturing", "Inventory, suppliers, equipment, approvals"], ["Education", "Students, classes, notices, reports"], ["Professional Services", "Client portals, delivery workflows, billing"]],
  },
  {
    t: "Market tailwinds support the timing",
    sub: "Low-code, digital process automation, and agentic AI are converging into software-defined operations.",
    visual: "cellx_market_ad.png",
    stats: true,
  },
  {
    t: "Public AI workflow comps show the investor pattern",
    sub: "The strongest signal is not AI alone. Public markets reward AI platforms tied to data, workflow, governance, and execution.",
    layout: "competition",
    matrix: true,
  },
  {
    t: "AI agent competitors leave an SMB operating gap",
    sub: "Most public comps target enterprise platforms, CRM suites, or heavy automation. CellX can enter through lean-team workflows.",
    layout: "competitorDeepDive",
  },
  {
    t: "SWOT: prototype strength must become paid proof",
    sub: "The investor story improves when CellX converts technical progress into customer traction and repeatable workflow assets.",
    layout: "swot",
  },
  {
    t: "Business model",
    sub: "A tiered subscription model with private deployment and implementation upside.",
    layout: "pricingLadder",
    pricing: true,
  },
  {
    t: "Go-to-market starts with one painful workflow",
    sub: "CellX should sell proof, not a generic platform: begin with high-ROI workflows and turn each pilot into a reusable template.",
    layout: "gtmEngine",
  },
  {
    t: "Revenue model has four monetization layers",
    sub: "The model combines predictable SaaS with high-touch setup, premium templates, and usage pass-through.",
    layout: "revenueModel",
  },
  {
    t: "Investor-case outlook reaches $6.0M ARR run-rate",
    sub: "A focused wedge can expand from paid pilots into recurring SaaS, implementation, templates, and partner channels.",
    layout: "financialOutlook",
  },
  {
    t: "Roadmap to paid pilots",
    sub: "Focus on universal business templates, governed execution, and one-person AI company workflows.",
    layout: "gtm",
    roadmap: true,
  },
  {
    t: "Thank you",
    sub: "CellX is ready for pilot discovery, technical hardening, and partner introductions.",
    layout: "ask",
    bullets: ["Pilot customers in marketing, e-commerce, operations, education, services, and SMB IT.", "Cloud credits and security mentorship for production workflow execution.", "Introductions to social media, marketplace, shipping, payment, and AI ecosystem partners.", "Goal: convert prototype momentum into paid pilots and reusable cross-industry workflow templates."],
  },
];

async function main() {
  await fs.mkdir(OUT, { recursive: true });
  const visualBytes = {};
  for (const name of ["cellx_hero_ad.png", "cellx_architecture.png", "cellx_workflow_ad.png", "cellx_market_ad.png"]) {
    visualBytes[name] = await fs.readFile(path.join(VIS, name));
  }
  const p = Presentation.create({ slideSize: { width: 1280, height: 720 } });

  for (const [idx, spec] of slides.entries()) {
    const s = p.slides.add();
    title(s, spec.t, spec.sub);
    tb(s, String(idx + 1).padStart(2, "0"), 1150, 660, 64, 28, { fontSize: 13, color: "#94A3B8", alignment: "right" });

    if (spec.kind === "cover") {
      s.images.add({ blob: visualBytes["cellx_hero_ad.png"], contentType: "image/png", alt: "CellX product advertising visual", fit: "cover", position: { left: 640, top: 176, width: 540, height: 304 }, borderRadius: "rounded-xl" });
      tb(s, "Competition Pitch Deck", 58, 230, 360, 36, { fontSize: 22, bold: true, color: C.blue });
      tb(s, "Presented by Harrison Huang and David Cai", 60, 274, 520, 24, { fontSize: 18, bold: true, color: C.navy });
      tb(s, "Tarbut V' Torah (TVT) Community Day School | 9th Grade", 60, 302, 560, 24, { fontSize: 15, color: C.muted });
      stat(s, "Public site", "cellaidata.com", 60, 326, 250, C.blue);
      stat(s, "Backend", "app.cellaidata.com", 335, 326, 270, C.cyan);
      tb(s, "Built around a real deployed prototype: software-defined apps, cross-industry workflows, CellX backend extension, and AI skill design.", 64, 515, 900, 56, { fontSize: 20, color: C.ink });
      drawBigIdeaStrip(s, 60, 588);
    } else if (spec.layout === "pain") {
      drawPainVisual(s);
    } else if (spec.layout === "product") {
      drawProductMockup(s);
    } else if (spec.layout === "library") {
      drawNodeLibrary(s);
    } else if (spec.layout === "db") {
      drawDbActivation(s);
    } else if (spec.layout === "aiModes") {
      drawAiModes(s);
    } else if (spec.layout === "customers") {
      drawCustomers(s);
    } else if (spec.layout === "competition") {
      drawCompetition(s);
    } else if (spec.layout === "competitorDeepDive") {
      drawCompetitorDeepDive(s);
    } else if (spec.layout === "swot") {
      drawSwot(s);
    } else if (spec.layout === "pricingLadder") {
      drawPricingLadder(s);
    } else if (spec.layout === "gtmEngine") {
      drawGtmEngine(s);
    } else if (spec.layout === "revenueModel") {
      drawRevenueModel(s);
    } else if (spec.layout === "financialOutlook") {
      drawFinancialOutlook(s);
    } else if (spec.layout === "gtm") {
      drawGtm(s);
    } else if (spec.layout === "ask") {
      drawAsk(s);
    } else if (spec.layout === "lifecycle") {
      drawBusinessLifecycle(s);
    } else if (spec.stats) {
      stat(s, "Gartner projected low-code development technologies market by 2029", "$58.2B", 70, 250, 330, C.blue);
      stat(s, "Forrester AI-fueled low-code/DPA upside scenario by 2028", "$50B", 475, 250, 330, C.purple);
      stat(s, "Deloitte: companies expecting to customize AI agents", "85%", 880, 250, 330, C.green);
      tb(s, "One buyer need is emerging: software-defined operations that let lean teams launch workflows, use AI agents, and reduce process cost.", 120, 405, 1040, 42, { fontSize: 22, bold: true, color: C.navy, alignment: "center" });
      drawBigIdeaStrip(s, 128, 500);
      tb(s, "Sources: Gartner 2025, Forrester 2024, Deloitte State of AI 2026, McKinsey 2026.", 82, 636, 1000, 30, { fontSize: 14, color: C.muted });
    } else if (spec.visual) {
      s.images.add({ blob: visualBytes[spec.visual], contentType: "image/png", alt: spec.t, fit: "contain", position: { left: 76, top: 218, width: 1128, height: 420 }, borderRadius: "rounded-xl" });
    } else if (spec.workflow) {
      workflowNode(s, "Order Created", "Trigger", 98, 312, C.blue, "/ext-api/workflows");
      workflowNode(s, "Payment Captured?", "Condition", 340, 312, C.orange, "payment_status == Captured");
      workflowNode(s, "AI Decision Agent", "AI", 582, 312, C.purple, "/ext-api/ai/workflows/run");
      workflowNode(s, "UPS / FedEx Rate", "Carrier", 582, 442, "#0891B2", "/ext-api/carriers/rates");
      workflowNode(s, "Update Order", "Action", 824, 375, C.green, "/prod-api/pagegenerator");
      arrow(s, 288, 354, 338, 354); arrow(s, 530, 354, 580, 354); arrow(s, 530, 376, 580, 470); arrow(s, 772, 354, 822, 403); arrow(s, 772, 470, 822, 417);
      tb(s, "Visual, testable, and extension-friendly", 96, 555, 980, 34, { fontSize: 24, bold: true, color: C.navy });
    } else if (spec.marketingFlow) {
      drawMarketingAutomation(s);
    } else if (spec.amazonFlow) {
      const xs = [58, 258, 458, 658, 858, 1058];
      [["Schedule", "Trigger", C.blue], ["Amazon Search", "Tool", C.navy], ["SKU + Price", "Amazon", "#334155"], ["Export Excel", "Data", C.green], ["ChatGPT Handoff", "AI", C.purple], ["Email Result", "Email", C.orange]].forEach((n, i) => {
        workflowNode(s, n[0], n[1], xs[i], 330, n[2], i === 4 ? "manual web handoff" : "");
        if (i < 5) arrow(s, xs[i] + 190, 372, xs[i + 1] - 2, 372);
      });
      tb(s, "No platform token burn in manual handoff mode; the user copies ChatGPT analysis back into the workflow.", 80, 505, 1080, 40, { fontSize: 20, color: C.ink });
    } else if (spec.matrix) {
      [["Generic low-code", "Fast UI, weaker backend-specific workflows"], ["SaaS automation", "Many connectors, less native data governance"], ["AI agent tools", "Great reasoning, often disconnected from enterprise data"], ["CellX RDP", "Generated apps + workflow + DB activation + AI modes"]].forEach((r, i) => {
        box(s, 100, 245 + i * 82, 1000, 58, i === 3 ? "#E8FFF3" : C.white, i === 3 ? "#86EFAC" : C.line);
        tb(s, r[0], 130, 260 + i * 82, 260, 22, { fontSize: 17, bold: true, color: i === 3 ? C.green : C.navy });
        tb(s, r[1], 410, 260 + i * 82, 620, 24, { fontSize: 16, color: C.ink });
      });
    } else if (spec.pricing) {
      [["Trial", "$0", "14-day demo and workflow preview"], ["Starter", "$99/mo", "20 pages, 1 production env"], ["Growth", "$299/mo", "Unlimited pages and workflow support"], ["Enterprise", "$899+/mo", "Private deployment and onboarding"]].forEach((r, i) => {
        box(s, 72 + i * 292, 270, 250, 190, C.white, C.line);
        tb(s, r[0], 100 + i * 292, 296, 190, 28, { fontSize: 20, bold: true, color: C.navy });
        tb(s, r[1], 100 + i * 292, 340, 190, 44, { fontSize: 30, bold: true, color: i === 0 ? C.green : C.blue });
        tb(s, r[2], 100 + i * 292, 405, 190, 54, { fontSize: 14, color: C.muted });
      });
    } else if (spec.roadmap) {
      [["0-3 mo", "Prototype hardening"], ["3-6 mo", "Production sidecar + connector tests"], ["6-12 mo", "Template marketplace + billing"], ["12-18 mo", "Partners + enterprise kit"]].forEach((r, i) => {
        s.shapes.add({ geometry: "ellipse", position: { left: 130 + i * 265, top: 320, width: 28, height: 28 }, fill: [C.blue, C.cyan, C.purple, C.green][i], line: { style: "solid", fill: "none", width: 0 } });
        if (i < 3) arrow(s, 158 + i * 265, 334, 382 + i * 265, 334);
        tb(s, r[0], 110 + i * 265, 370, 110, 24, { fontSize: 18, bold: true, color: C.navy, alignment: "center" });
        tb(s, r[1], 70 + i * 265, 405, 190, 48, { fontSize: 15, color: C.muted, alignment: "center" });
      });
    } else if (spec.cards) {
      spec.cards.forEach((card, i) => {
        const col = i % 3, row = Math.floor(i / 3);
        box(s, 72 + col * 380, 255 + row * 140, 330, 100, C.white, C.line);
        tb(s, card[0], 96 + col * 380, 278 + row * 140, 280, 24, { fontSize: 18, bold: true, color: C.navy });
        tb(s, card[1], 96 + col * 380, 315 + row * 140, 280, 36, { fontSize: 14, color: C.muted });
      });
    } else if (spec.bullets) {
      bulletList(s, spec.bullets, 100, 260, 950, 72);
    }

    s.speakerNotes.textFrame.setText([
      `Slide ${idx + 1}: ${spec.t}`,
      "Talk track: connect the prototype to concrete customer pain and show how CellX keeps the core backend stable while adding workflow and AI capability.",
      "Sources used where applicable: Gartner low-code forecast, Forrester low-code market analysis, Deloitte State of AI 2026, McKinsey agentic AI infrastructure article."
    ]);
    s.speakerNotes.setVisible(true);
  }

  const montage = await p.export({ format: "webp", montage: true, scale: 1 });
  await writeBlob(path.join(OUT, "pitch_deck_montage.webp"), montage);
  for (const [i, slide] of p.slides.items.entries()) {
    const png = await p.export({ slide, format: "png", scale: 1 });
    await writeBlob(path.join(OUT, `slide-${String(i + 1).padStart(2, "0")}.png`), png);
  }
  const pptx = await PresentationFile.exportPptx(p);
  await pptx.save(PPTX);
  console.log(path.resolve(PPTX));
}

main().catch((err) => {
  console.error(err);
  process.exitCode = 1;
});
