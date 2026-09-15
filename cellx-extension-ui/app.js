// Keep localized status descriptors separate from serialized workflow messages.
const agentUiMessages = new Map();

function uiMessage(english, params = {}, dates = {}) {
  const message = english.replace(/\{(\w+)\}/g, (match, key) =>
    Object.prototype.hasOwnProperty.call(params, key) ? String(params[key]) : match);
  agentUiMessages.set(message, { english, params, dates });
  return message;
}

function uiSource(english, params) {
  const message = agentUiMessages.get(english);
  if (!message) return { english, params };
  return { english: message.english, params: {
    ...message.params,
    ...Object.fromEntries(Object.entries(message.dates).map(([key, [value, options]]) => [key, uiDate(value, options)])),
  } };
}

// Translate presentation only; workflow names, settings and API payloads stay in English.
function agentT(english, params = {}) {
  ({ english, params } = uiSource(english, params));
  if (window.CellI18n?.t) return window.CellI18n.t(english, params);
  return String(english).replace(/\{(\w+)\}/g, (match, key) =>
    Object.prototype.hasOwnProperty.call(params, key) ? String(params[key]) : match);
}

// Only authored help is localized; example code, URLs, IDs and timezone strings are not.
const integrationPlaceholderSources = new Set([
  "client_id from provider console",
  "store in backend secret manager",
  "read/write permissions requested",
  "provider API key",
  "optional custom API endpoint",
  "verify inbound webhook signatures",
  "Choose who owns usage and billing",
  "stored per customer/user in backend secret storage",
  "optional OpenAI-compatible endpoint",
  "optional project, org, or workspace id",
  "Use {{order}}, {{customer}}, {{previous_step}} placeholders",
  "JSON fields the model should return",
  "Paste ChatGPT JSON output here after running the copied prompt",
  "mask PII, customer consent, or internal-only context",
  "Which data enters this rule",
  "for example payment_status, total, shipping_country",
  "Comparison operator",
  "for example Captured, 100, US",
  "Yes / matched",
  "No / fallback",
  "What to do when no items exist",
  "Duration or exact time",
  "15 minutes, 2 hours, 1 day",
  "What happens after waiting",
  "Retry spacing",
  "30 seconds",
  "Exception / Manual Review",
  "Workflow result",
  "Why this path should stop.",
  "Operations Manager",
  "Please review this order exception.",
  "Approve",
  "Reject",
  "24 hours",
  "preview or connected provider",
  "your Gmail address",
  "same as Gmail username",
  "+1 Twilio phone number, optional",
  "CRUD action",
  "id or uuid",
  "Prefer soft delete",
  "Execution guardrail",
  "shipping account number",
  "FedEx developer project key",
  "FedEx developer project secret",
  "sandbox or production",
  "UPS app client id",
  "UPS app client secret",
  "UPS shipper number",
  "optional billing account",
  "USPS developer app client id",
  "USPS developer app secret",
  "optional USPS mailer id",
  "DHL billing account",
  "DHL developer key",
  "DHL developer secret",
  "optional acct_...",
  "live app client id",
  "live app secret",
  "PayPal merchant id",
  "sandbox or live",
  "Amazon seller id",
  "for example ATVPDKIKX0DER",
  "Login with Amazon client id",
  "Login with Amazon secret",
  "seller authorization refresh token",
  "IAM role used by SP-API app",
  "for example us-east-1",
  "used to verify webhooks",
  "127.0.0.1 or database host",
  "least-privilege database user",
  "database password",
  "optional team or operator",
  "previous_step or previous_step.result",
  "object or rows",
  "How Google access is provided",
  "Google Sheet ID from the URL",
  "Form Submissions",
  "Append or replace rows",
  "Sheet Column <- workflow_field",
  "optional backend/service account credential",
  "optional server-to-server credential",
  "common, organizations, or tenant id",
  "workspace, phone, or business id",
  "bot token or access token",
  "company instance or subdomain",
  "target API or internal endpoint",
  "Bearer token or signed header",
  "3 retries, exponential backoff",
  "Customer Lead Scoring Agent",
  "Where this agent executes",
  "API, webhook, script, or MCP-style",
  "Use cached clone",
  "How to authenticate",
  "Dry run is safer for setup",
  "2 retries, exponential backoff",
  "Store ID from Order Desk API settings",
  "API Key from Order Desk API settings",
  "optional space-separated args",
  "team or operator responsible",
  "model name",
  "provider chat console URL",
  "If order.total > 100 route to approval.",
  "Describe the decision in plain English.",
  "Choose a CellX table"
]);

function uiPlaceholder(placeholder) {
  const source = String(placeholder ?? "");
  if (!integrationPlaceholderSources.has(source)) return `placeholder="${escapeHtml(source)}"`;
  return `data-agent-i18n-attributes data-i18n-placeholder="${escapeHtml(source)}" placeholder="${escapeHtml(agentT(source))}"`;
}

function uiIntegrationTitle(spec, node) {
  if (spec.title === `${node.name} Rule`) return uiLabel("{name} Rule", { name: node.name });
  const provider = aiProviderFromNode(node);
  if (spec.title === `${provider} Model Step`) return uiLabel("{provider} Model Step", { provider });
  const emailProvider = node.name.includes("Gmail") ? "Gmail" : node.name.includes("Outlook") ? "Outlook" : "Email";
  if (spec.title === `${emailProvider} Customer Email`) return uiLabel("{provider} Customer Email", { provider: emailProvider });
  return uiLabel(spec.title);
}

function uiAttrs(english, params = {}) {
  const message = agentUiMessages.has(english) ? `data-agent-message="${escapeHtml(english)}" ` : "";
  ({ english, params } = uiSource(english, params));
  return `${message}data-agent-i18n data-i18n="${escapeHtml(english)}" data-i18n-params="${escapeHtml(JSON.stringify(params))}"`;
}

function uiLabel(english, params = {}) {
  return `<span ${uiAttrs(english, params)}>${escapeHtml(agentT(english, params))}</span>`;
}

function uiText(element, english, params = {}) {
  if (!element) return;
  if (agentUiMessages.has(english)) element.setAttribute("data-agent-message", english);
  else element.removeAttribute("data-agent-message");
  ({ english, params } = uiSource(english, params));
  element.setAttribute("data-agent-i18n", "");
  element.setAttribute("data-i18n", english);
  element.setAttribute("data-i18n-params", JSON.stringify(params));
  if (window.CellI18n?.text) window.CellI18n.text(element, english, params);
  else element.textContent = agentT(english, params);
}

function uiDate(value, options) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return window.CellI18n?.formatDate
    ? window.CellI18n.formatDate(date, options || undefined)
    : options ? date.toLocaleString("en-US", options) : date.toLocaleString();
}

function uiDateMarkup(value, options) {
  if (!value) return "";
  return `<span data-agent-date="${escapeHtml(value)}" data-agent-date-options="${escapeHtml(JSON.stringify(options || null))}">${escapeHtml(uiDate(value, options))}</span>`;
}

// Only explicitly owned text/attributes are refreshed. Never recreate forms or result data.
window.addEventListener("cell-language-change", () => {
  document.querySelectorAll("[data-agent-message]").forEach(element => uiText(element, element.getAttribute("data-agent-message")));
  document.querySelectorAll("[data-agent-i18n]").forEach(element => {
    const params = JSON.parse(element.getAttribute("data-i18n-params") || "{}");
    element.textContent = agentT(element.getAttribute("data-i18n"), params);
  });
  document.querySelectorAll("[data-agent-i18n-attributes]").forEach(element => {
    for (const attribute of ["placeholder", "title", "aria-label"]) {
      const source = element.getAttribute(`data-i18n-${attribute}`);
      if (source !== null) element.setAttribute(attribute, agentT(source));
    }
  });
  document.querySelectorAll("[data-agent-date]").forEach(element => {
    element.textContent = uiDate(element.getAttribute("data-agent-date"),
      JSON.parse(element.getAttribute("data-agent-date-options") || "null"));
  });
  const timeInput = propIntegration?.querySelector("[data-daily-run-time]");
  if (timeInput?.validity.customError) timeInput.setCustomValidity(agentT("Choose a valid daily run time."));
});

const apiBase = "/ext-api";
const canvas = document.getElementById("canvas");
const linksSvg = document.getElementById("links");
const connectBtn = document.getElementById("connectModeBtn");
const propName = document.getElementById("propName");
const propType = document.getElementById("propType");
const propAction = document.getElementById("propAction");
const propNotes = document.getElementById("propNotes");
const propIntegration = document.getElementById("integrationFields");
const propertyActionBar = document.getElementById("propertyActionBar");
const workflowTitleEl = document.getElementById("workflowTitle");
const workflowDescriptionEl = document.getElementById("workflowDescription");
const workflowTabsEl = document.getElementById("workflowTabs");
const workflowResultTabsHost = document.getElementById("workflowResultTabsHost");
const aiVoiceBuilderPanel = document.getElementById("aiVoiceBuilderPanel");
const aiVoicePromptEl = document.getElementById("aiVoicePrompt");
const aiVoiceStatusEl = document.getElementById("aiVoiceStatus");
const aiVoiceDraftPreviewEl = document.getElementById("aiVoiceDraftPreview");
const aiVoiceDraftMetaEl = document.getElementById("aiVoiceDraftMeta");
const importAiDraftBtn = document.getElementById("importAiDraftBtn");
const templateBrowser = document.getElementById("templateBrowser");
const templateListEl = document.getElementById("templateList");
const templateSearchEl = document.getElementById("templateSearch");
const templateCategoryFilterEl = document.getElementById("templateCategoryFilter");
const templateLibraryStatusEl = document.getElementById("templateLibraryStatus");
const templateManagerPanel = document.getElementById("templateManagerPanel");
const templateManagerStatusEl = document.getElementById("templateManagerStatus");
const managedTemplateListEl = document.getElementById("managedTemplateList");
const managedScriptListEl = document.getElementById("managedScriptList");
const managedTimerListEl = document.getElementById("managedTimerList");
const managedTemplateCountEl = document.getElementById("managedTemplateCount");
const managedScriptCountEl = document.getElementById("managedScriptCount");
const managedTimerCountEl = document.getElementById("managedTimerCount");
const marketplacePanel = document.getElementById("marketplacePanel");
const marketplaceListEl = document.getElementById("marketplaceList");
const marketplaceStatusEl = document.getElementById("marketplaceStatus");
const marketplaceSearchEl = document.getElementById("marketplaceSearch");
const marketplaceCategoryFilterEl = document.getElementById("marketplaceCategoryFilter");
const marketplaceAccountStatusEl = document.getElementById("marketplaceAccountStatus");

let nodes = [];
let links = [];
let workflows = [];
let templateLibrary = [];
let templateManagerState = { templates: [], scripts: [], timers: [] };
let marketplaceItems = [];
let aiWorkflowDraft = null;
let activeWorkflowId = null;
let selectedId = null;
let activeResultNodeId = null;
let connectMode = false;
let connectFrom = null;
let dragState = null;
let nextId = 1;
let cellxSchema = { tables: [] };
let workflowTitle = "Order Fulfillment Flow";
let workflowDescription = "Drag nodes, reposition them, then connect steps.";
const templateVersion = "1.0";
const templateManifestPath = "./workflow-templates/manifest.json";
const workflowStoreKey = "cellx-workflows-draft";
const legacyWorkflowStoreKey = "cellx-workflow-draft";
const nodeConfigStoreKey = "cellx-workflow-node-configs";
const marketplaceStoreKey = "cellx-workflow-marketplace-draft";
const marketplaceDeletedStoreKey = "cellx-marketplace-hidden-templates";
const marketplaceUserStoreKey = "cellx-marketplace-user";
const marketplaceTokenStoreKey = "cellx-marketplace-token";
const workflowManagementTokenStoreKey = "cellx-workflow-management-token";
const sensitiveSettingPattern = /(apiKey|secretKey|clientSecret|authHeader|authToken|bearerToken|apiToken|password|token|serviceAccountJson)$/i;
const defaultEmailRecipient = "workad_009@icloud.com";
const nodeWidth = 188;
const nodeHeight = 96;

function isNarrowScreen() {
  return window.matchMedia("(max-width: 720px)").matches;
}

function canvasSize() {
  return {
    width: Math.max(360, canvas.clientWidth || 0),
    height: Math.max(420, canvas.clientHeight || 0),
  };
}

function fitNodesToCanvas() {
  if (!nodes.length || dragState) return;
  const { width, height } = canvasSize();
  const pad = isNarrowScreen() ? 28 : 70;
  const minX = Math.min(...nodes.map((node) => node.x));
  const maxX = Math.max(...nodes.map((node) => node.x));
  const minY = Math.min(...nodes.map((node) => node.y));
  const maxY = Math.max(...nodes.map((node) => node.y));
  const targetXRange = Math.max(1, width - pad * 2 - nodeWidth);
  const targetYRange = Math.max(1, height - pad * 2 - nodeHeight);
  const xRange = Math.max(1, maxX - minX);
  const yRange = Math.max(1, maxY - minY);

  if (xRange > targetXRange || minX < pad || maxX + nodeWidth > width - pad) {
    const gap = 36;
    const availableWidth = Math.max(nodeWidth, width - pad * 2);
    const cols = Math.max(2, Math.floor((availableWidth + gap) / (nodeWidth + gap)));
    const usableRange = cols === 1 ? 0 : Math.max(0, availableWidth - nodeWidth);
    const colStep = cols === 1 ? 0 : usableRange / (cols - 1);
    workflowOrder().forEach((node, index) => {
      const col = index % cols;
      const row = Math.floor(index / cols);
      node.x = Math.round(pad + col * colStep);
      node.y = Math.max(node.y, pad + row * 150);
    });
  }

  const nextMinY = Math.min(...nodes.map((node) => node.y));
  const nextMaxY = Math.max(...nodes.map((node) => node.y));
  if (yRange > targetYRange || minY < pad || maxY + nodeHeight > height - pad) {
    const shift = nextMinY < pad ? pad - nextMinY : nextMaxY + nodeHeight > height - pad ? height - pad - nodeHeight - nextMaxY : 0;
    if (shift) nodes.forEach((node) => { node.y = Math.max(pad, Math.round(node.y + shift)); });
  }
}

function autoLayoutPositions() {
  if (isNarrowScreen()) {
    return [[44, 38], [44, 150], [44, 262], [44, 374], [44, 486], [44, 598]];
  }
  const { width } = canvasSize();
  const left = 70;
  const right = Math.max(left, width - nodeWidth - 72);
  const step = Math.max(210, Math.min(260, (right - left) / 3));
  const col1 = left;
  const col2 = Math.round(Math.min(right, left + step));
  const col3 = Math.round(Math.min(right, left + step * 2));
  const col4 = Math.round(right);
  return [[col1, 90], [col2, 90], [col3, 90], [col3, 260], [col4, 175], [col4, 345]];
}

function updateCanvasExtent() {
  const pad = isNarrowScreen() ? 44 : 80;
  const maxX = nodes.length ? Math.max(...nodes.map((node) => node.x + nodeWidth + pad)) : canvas.clientWidth;
  const maxY = nodes.length ? Math.max(...nodes.map((node) => node.y + nodeHeight + pad)) : canvas.clientHeight;
  linksSvg.style.width = `${Math.max(canvas.clientWidth, maxX)}px`;
  linksSvg.style.height = `${Math.max(canvas.clientHeight, maxY)}px`;
}

const nodeCatalog = [
  {
    group: "Triggers",
    children: [
      {
        name: "Order Created",
        type: "trigger",
        sub: "Orders",
        desc: "Start when a new order enters CellX.",
        action: "/ext-api/workflows/order-created",
      },
      {
        name: "Payment Captured",
        type: "trigger",
        sub: "Payments",
        desc: "Start after Stripe, PayPal, or card payment settles.",
        action: "/ext-api/payments/captured",
      },
      {
        name: "Webhook Received",
        type: "trigger",
        sub: "Developer",
        desc: "Start from any third-party HTTP callback.",
        action: "/ext-api/webhooks/inbound",
      },
      {
        name: "Schedule",
        type: "trigger",
        sub: "System",
        desc: "Run every hour, day, week, or month.",
        action: "cron",
      },
    ],
  },
  {
    group: "Logic & Control",
    children: [
      { name: "If / Else Branch", type: "condition", sub: "Branching", desc: "Route data into yes/no paths based on a rule.", action: "if condition then true_path else false_path" },
      { name: "Switch / Match", type: "condition", sub: "Branching", desc: "Choose one of many paths from a field value.", action: "switch field by matching cases" },
      { name: "Filter Records", type: "condition", sub: "Branching", desc: "Continue only when rows match the filter.", action: "filter records where rule is true" },
      { name: "Value Compare", type: "condition", sub: "Branching", desc: "Compare numbers, dates, text, status, or totals.", action: "left_value operator right_value" },
      { name: "Loop Items", type: "control", sub: "Loop", desc: "Run the next steps for every order line or record.", action: "for each item in collection" },
      { name: "Wait / Delay", type: "control", sub: "Timing", desc: "Pause a workflow for minutes, hours, or until a date.", action: "delay duration" },
      { name: "Human Approval", type: "control", sub: "Approval", desc: "Pause until an operator approves, rejects, or edits.", action: "/ext-api/tools/approval" },
      { name: "Stop Workflow", type: "control", sub: "Stop", desc: "End the flow intentionally with a final status.", action: "stop workflow with reason" },
      { name: "Retry / Error Handler", type: "control", sub: "Error Handling", desc: "Retry failed steps or route to an exception path.", action: "retry failed step" },
    ],
  },
  {
    group: "Office & Documents",
    children: [
      { name: "Google Docs", type: "document", sub: "Google Workspace", desc: "Create, update, or summarize documents.", action: "/ext-api/google/docs" },
      { name: "Google Sheets", type: "document", sub: "Google Workspace", desc: "Read/write spreadsheet rows and import orders.", action: "/ext-api/google/sheets" },
      { name: "Google Forms", type: "document", sub: "Google Workspace", desc: "Collect requests, returns, and survey responses.", action: "/ext-api/google/forms" },
      { name: "Google Slides", type: "document", sub: "Google Workspace", desc: "Generate partner decks and operations reports.", action: "/ext-api/google/slides" },
      { name: "Google Drive", type: "document", sub: "Google Workspace", desc: "Store labels, invoices, and order files.", action: "/ext-api/google/drive" },
      { name: "Microsoft Word", type: "document", sub: "Microsoft 365", desc: "Generate docs, quotes, or SOP files.", action: "/ext-api/microsoft/word" },
      { name: "Microsoft Excel", type: "document", sub: "Microsoft 365", desc: "Export reports and reconcile imports.", action: "/ext-api/microsoft/excel" },
      { name: "OneDrive", type: "document", sub: "Microsoft 365", desc: "Sync customer files and generated documents.", action: "/ext-api/microsoft/onedrive" },
      { name: "SharePoint", type: "document", sub: "Microsoft 365", desc: "Publish shared files and internal documents.", action: "/ext-api/microsoft/sharepoint" },
      { name: "Box", type: "document", sub: "Files", desc: "Store enterprise documents and customer assets.", action: "/ext-api/box/files" },
      { name: "Dropbox", type: "document", sub: "Files", desc: "Attach artwork, labels, and external files.", action: "/ext-api/dropbox/files" },
      { name: "Notion", type: "document", sub: "Knowledge Base", desc: "Write support docs and internal workflow notes.", action: "/ext-api/notion/pages" },
      { name: "Airtable", type: "document", sub: "Database Sheets", desc: "Sync lightweight operational records.", action: "/ext-api/airtable/records" },
    ],
  },
  {
    group: "Email, Calendar & Chat",
    children: [
      { name: "Outlook Email", type: "communication", sub: "Microsoft 365", desc: "Send customer or operator emails.", action: "/ext-api/outlook/mail" },
      { name: "Outlook Calendar", type: "communication", sub: "Microsoft 365", desc: "Create follow-up events and reminders.", action: "/ext-api/outlook/calendar" },
      { name: "Gmail", type: "communication", sub: "Google Workspace", desc: "Send order, refund, or exception emails.", action: "/ext-api/gmail/send" },
      { name: "Google Calendar", type: "communication", sub: "Google Workspace", desc: "Schedule operations and reminders.", action: "/ext-api/google/calendar" },
      { name: "Slack", type: "communication", sub: "Team Chat", desc: "Notify fulfillment and support channels.", action: "/ext-api/slack/message" },
      { name: "Microsoft Teams", type: "communication", sub: "Team Chat", desc: "Post approvals and exception alerts.", action: "/ext-api/teams/message" },
      { name: "Discord", type: "communication", sub: "Team Chat", desc: "Send team or community notifications.", action: "/ext-api/discord/message" },
      { name: "Telegram Bot", type: "communication", sub: "Messaging", desc: "Push alerts to Telegram chats and groups.", action: "/ext-api/telegram/send" },
      { name: "WhatsApp Business", type: "communication", sub: "Messaging", desc: "Send customer updates through WhatsApp.", action: "/ext-api/whatsapp/send" },
      { name: "Twilio SMS", type: "communication", sub: "Messaging", desc: "Send SMS verification and shipping updates.", action: "/ext-api/twilio/sms" },
      { name: "Mailchimp", type: "communication", sub: "Marketing", desc: "Add contacts and trigger email campaigns.", action: "/ext-api/mailchimp" },
      { name: "LinkedIn", type: "communication", sub: "Marketing", desc: "Route lead and campaign events.", action: "/ext-api/linkedin" },
    ],
  },
  {
    group: "Commerce, CRM & Support",
    children: [
      { name: "Shopify", type: "commerce", sub: "Commerce", desc: "Sync orders, customers, products, and fulfillment.", action: "/ext-api/shopify/sync" },
      { name: "WooCommerce", type: "commerce", sub: "Commerce", desc: "Sync WordPress store orders.", action: "/ext-api/woocommerce/sync" },
      { name: "Magento", type: "commerce", sub: "Commerce", desc: "Sync catalog, orders, and customers.", action: "/ext-api/magento/sync" },
      { name: "Walmart Marketplace", type: "commerce", sub: "Marketplace", desc: "Import marketplace orders and inventory events.", action: "/ext-api/walmart/orders" },
      { name: "Amazon SP-API", type: "amazon", sub: "Marketplace", desc: "Sync Amazon orders and fulfillment updates.", action: "/ext-api/amazon/orders/sync" },
      { name: "eBay", type: "commerce", sub: "Marketplace", desc: "Import marketplace orders and tracking.", action: "/ext-api/ebay/orders" },
      { name: "HubSpot", type: "crm", sub: "CRM", desc: "Create deals, contacts, and service tickets.", action: "/ext-api/hubspot/sync" },
      { name: "Salesforce", type: "crm", sub: "CRM", desc: "Sync accounts, opportunities, and cases.", action: "/ext-api/salesforce/sync" },
      { name: "Pipedrive", type: "crm", sub: "CRM", desc: "Move deals as orders progress.", action: "/ext-api/pipedrive/sync" },
      { name: "Zoho CRM", type: "crm", sub: "CRM", desc: "Sync leads, contacts, and accounts.", action: "/ext-api/zoho/crm" },
      { name: "Zendesk", type: "support", sub: "Support", desc: "Open support tickets from order exceptions.", action: "/ext-api/zendesk/tickets" },
      { name: "Intercom", type: "support", sub: "Support", desc: "Send customer support events and messages.", action: "/ext-api/intercom/events" },
      { name: "Freshdesk", type: "support", sub: "Support", desc: "Create tickets for customer issues.", action: "/ext-api/freshdesk/tickets" },
    ],
  },
  {
    group: "Shipping, Payment & Accounting",
    children: [
      { name: "FedEx", type: "carrier", sub: "Shipping", desc: "Rates, labels, tracking, and delivery events.", action: "/ext-api/fedex" },
      { name: "UPS", type: "carrier", sub: "Shipping", desc: "Rates, labels, tracking, and pickup workflows.", action: "/ext-api/ups" },
      { name: "USPS", type: "carrier", sub: "Shipping", desc: "Domestic labels and tracking updates.", action: "/ext-api/usps" },
      { name: "DHL", type: "carrier", sub: "Shipping", desc: "International labels and customs paperwork.", action: "/ext-api/dhl" },
      { name: "Stripe", type: "payment", sub: "Payments", desc: "Payment intents, refunds, and webhooks.", action: "/ext-api/stripe" },
      { name: "PayPal", type: "payment", sub: "Payments", desc: "Checkout, capture, refunds, and disputes.", action: "/ext-api/paypal" },
      { name: "Square", type: "payment", sub: "Payments", desc: "Payment capture and point-of-sale sync.", action: "/ext-api/square" },
      { name: "QuickBooks", type: "finance", sub: "Accounting", desc: "Invoices, customers, and accounting sync.", action: "/ext-api/quickbooks" },
      { name: "Xero", type: "finance", sub: "Accounting", desc: "Accounting records and reconciliation.", action: "/ext-api/xero" },
    ],
  },
  {
    group: "Data, DevOps & Internal Systems",
    children: [
      { name: "MySQL", type: "database", sub: "Database", desc: "Query operational tables with approved SQL.", action: "/ext-api/database/mysql" },
      { name: "PostgreSQL", type: "database", sub: "Database", desc: "Read and write Postgres data sources.", action: "/ext-api/database/postgres" },
      { name: "MongoDB", type: "database", sub: "Database", desc: "Sync document records and events.", action: "/ext-api/database/mongodb" },
      { name: "Redis", type: "database", sub: "Cache", desc: "Read cache keys and publish queue events.", action: "/ext-api/redis" },
      { name: "GitHub", type: "tool", sub: "Developer", desc: "Open issues, sync releases, and trigger actions.", action: "/ext-api/github" },
      { name: "GitLab", type: "tool", sub: "Developer", desc: "Create issues and run CI/CD hooks.", action: "/ext-api/gitlab" },
      { name: "Jira", type: "tool", sub: "Developer", desc: "Create tickets from workflow exceptions.", action: "/ext-api/jira" },
      { name: "AWS Lambda", type: "tool", sub: "Cloud", desc: "Run serverless tasks from a workflow.", action: "/ext-api/aws/lambda" },
    ],
  },
  {
    group: "CellX Database",
    children: [
      { name: "CellX Query Table", type: "cellx-db", sub: "CRUD Actions", desc: "Read CellX rows with filters, sorting, and pagination.", action: "/ext-api/cellx-db/query" },
      { name: "CellX Get Detail", type: "cellx-db", sub: "CRUD Actions", desc: "Read one CellX record by primary key or business key.", action: "/ext-api/cellx-db/detail" },
      { name: "CellX Insert Row", type: "cellx-db", sub: "CRUD Actions", desc: "Create a new row in an approved CellX table.", action: "/ext-api/cellx-db/insert" },
      { name: "CellX Update Row", type: "cellx-db", sub: "CRUD Actions", desc: "Update selected fields for matched CellX rows.", action: "/ext-api/cellx-db/update" },
      { name: "CellX Delete Row", type: "cellx-db", sub: "CRUD Actions", desc: "Soft delete or delete approved CellX rows with safeguards.", action: "/ext-api/cellx-db/delete" },
      { name: "CellX Upsert Row", type: "cellx-db", sub: "CRUD Actions", desc: "Insert when missing, update when a matching key exists.", action: "/ext-api/cellx-db/upsert" },
      { name: "CellX Bulk Import", type: "cellx-db", sub: "Bulk Operations", desc: "Import validated Excel or JSON data into CellX tables.", action: "/ext-api/cellx-db/bulk-import" },
      { name: "CellX Export Excel", type: "cellx-db", sub: "Bulk Operations", desc: "Export CellX query results to an Excel workbook.", action: "/ext-api/cellx-db/export-excel" },
      { name: "Order Table: cx_order", type: "cellx-db", sub: "Core Tables", desc: "Read or update order records for workflow automations.", action: "/ext-api/cellx-db/table/cx_order" },
      { name: "Order Management: cx_orders_management", type: "cellx-db", sub: "Core Tables", desc: "Access the custom order management page data.", action: "/ext-api/cellx-db/table/cx_orders_management" },
      { name: "Page Config: gen_table", type: "cellx-db", sub: "Platform Tables", desc: "Read generated page/table definitions.", action: "/ext-api/cellx-db/table/gen_table" },
      { name: "Field Config: gen_table_column", type: "cellx-db", sub: "Platform Tables", desc: "Read or update generated field metadata.", action: "/ext-api/cellx-db/table/gen_table_column" },
      { name: "Workflow Log: cx_workflow_log", type: "cellx-db", sub: "Logs", desc: "Write workflow run events, decisions, and API outcomes.", action: "/ext-api/cellx-db/table/cx_workflow_log" },
    ],
  },
  {
    group: "AI Models",
    children: [
      { name: "OpenAI GPT-5.6", type: "ai", sub: "OpenAI", desc: "Latest flagship reasoning for agentic workflows.", action: "/ext-api/ai/openai/gpt-5.6" },
      { name: "OpenAI GPT-5", type: "ai", sub: "OpenAI", desc: "Reasoning, coding, agentic business workflows.", action: "/ext-api/ai/openai/gpt-5" },
      { name: "OpenAI GPT-5 mini", type: "ai", sub: "OpenAI", desc: "Lower cost automation and extraction.", action: "/ext-api/ai/openai/gpt-5-mini" },
      { name: "Claude Sonnet 5", type: "ai", sub: "Anthropic", desc: "Fast agentic work, coding, and writing.", action: "/ext-api/ai/anthropic/sonnet-5" },
      { name: "Claude Opus 5", type: "ai", sub: "Anthropic", desc: "Heavy reasoning and long-running agents.", action: "/ext-api/ai/anthropic/opus-5" },
      { name: "Google Gemini", type: "ai", sub: "Google", desc: "Multimodal reasoning and Workspace context.", action: "/ext-api/ai/google/gemini" },
      { name: "DeepSeek", type: "ai", sub: "Open models", desc: "Cost-sensitive reasoning and coding workflows.", action: "/ext-api/ai/deepseek" },
      { name: "Mistral", type: "ai", sub: "Open models", desc: "Fast multilingual workflows and extraction.", action: "/ext-api/ai/mistral" },
      { name: "Llama", type: "ai", sub: "Open models", desc: "Self-hosted or private model experiments.", action: "/ext-api/ai/llama" },
      { name: "Perplexity", type: "ai", sub: "Research", desc: "Research answers with web-grounded context.", action: "/ext-api/ai/perplexity" },
      { name: "Ollama Local Model", type: "ai", sub: "Local", desc: "Run local models for private experiments.", action: "/ext-api/ai/ollama" },
    ],
  },
  {
    group: "Agent Skills & Tools",
    children: [
      { name: "Video Generation", type: "script", sub: "Media", desc: "Product video with photo uploads, ad styles and background music.", action: "/ext-api/promo-videos" },
      { name: "External Agent", type: "external-agent", sub: "Developer", desc: "Call a third-party agent by API, webhook, script, or MCP-style contract.", action: "/ext-api/external-agent/run" },
      { name: "GitHub External Agent", type: "external-agent", sub: "Developer", desc: "Clone an approved GitHub AI agent repo, map JSON input, and run a configured command.", action: "/ext-api/external-agent/run" },
      { name: "HTTP Request", type: "tool", sub: "Developer", desc: "Call any REST API endpoint.", action: "/ext-api/tools/http" },
      { name: "Custom Script / Program", type: "script", sub: "Developer", desc: "Run a customer-provided script from the approved backend script folder.", action: "/ext-api/scripts/run" },
      { name: "Webhook Reply", type: "tool", sub: "Developer", desc: "Return data back to the caller.", action: "/ext-api/tools/webhook-reply" },
      { name: "SQL Query", type: "tool", sub: "Database", desc: "Read or update approved CellX tables.", action: "/ext-api/tools/sql" },
      { name: "JSON Transform", type: "tool", sub: "Data", desc: "Map source payloads into CellX fields.", action: "/ext-api/tools/json-transform" },
      { name: "Excel Import Parser", type: "tool", sub: "Data", desc: "Validate uploaded Excel order templates.", action: "/ext-api/tools/excel-import" },
      { name: "PDF / Invoice Reader", type: "tool", sub: "Documents", desc: "Extract order data from invoices and PDFs.", action: "/ext-api/tools/pdf-reader" },
      { name: "Human Approval", type: "tool", sub: "Control", desc: "Pause until an operator approves the next step.", action: "/ext-api/tools/approval" },
      { name: "Retry / Error Handler", type: "tool", sub: "Control", desc: "Retry failed API calls and write logs.", action: "/ext-api/tools/retry" },
    ],
  },
];

const typeDefaults = {
  trigger: { name: "Order Created", action: "/ext-api/workflows", notes: "Start when a new order enters CellX." },
  condition: { name: "Payment Captured?", action: "payment_status == Captured", notes: "Branch only paid orders to fulfillment." },
  control: { name: "Human Approval", action: "/ext-api/tools/approval", notes: "Pause the workflow until a user approves the next step." },
  carrier: { name: "UPS / FedEx Rate", action: "/ext-api/carriers/rates", notes: "Compare carrier rates and services." },
  amazon: { name: "Amazon SP-API Sync", action: "/ext-api/amazon/orders/sync", notes: "Sync marketplace order and fulfillment data." },
  ai: { name: "AI Decision Agent", action: "/ext-api/ai/workflows/run", notes: "Classify risk, suggest tags, and propose next actions." },
  document: { name: "Document Action", action: "/ext-api/documents", notes: "Read, write, or summarize business documents." },
  communication: { name: "Message Action", action: "/ext-api/messages", notes: "Send or receive email, calendar, chat, and SMS events." },
  commerce: { name: "Commerce Sync", action: "/ext-api/commerce", notes: "Sync orders, customers, products, and fulfillments." },
  crm: { name: "CRM Sync", action: "/ext-api/crm", notes: "Sync accounts, contacts, deals, and support context." },
  support: { name: "Support Ticket", action: "/ext-api/support", notes: "Create or update customer support tickets." },
  payment: { name: "Payment Action", action: "/ext-api/payments", notes: "Capture, refund, or reconcile payments." },
  finance: { name: "Accounting Sync", action: "/ext-api/accounting", notes: "Sync invoices, customers, and accounting entries." },
  database: { name: "Database Step", action: "/ext-api/database", notes: "Read or write an approved business data source." },
  "cellx-db": { name: "CellX Query Table", action: "/ext-api/cellx-db/query", notes: "Read or write approved CellX database tables through workflow safeguards." },
  "external-agent": { name: "External Agent", action: "/ext-api/external-agent/run", notes: "Connect a customer-owned API, webhook, script, or MCP-style agent to this workflow." },
  tool: { name: "Agent Tool", action: "/ext-api/tools", notes: "Execute a utility step inside an agent workflow." },
  script: { name: "Custom Script / Program", action: "/ext-api/scripts/run", notes: "Run an approved customer script and use its JSON output in the workflow." },
  action: { name: "Update Order Status", action: "/prod-api/pagegenerator/page/cx_order", notes: "Write status changes back to the order table." },
  log: { name: "Write History Log", action: "cx_order_history", notes: "Append an auditable workflow event." },
};

const categoryIcons = {
  "Triggers": "material-symbols:play-circle-outline-rounded",
  "Logic & Control": "material-symbols:account-tree-outline-rounded",
  "Office & Documents": "fluent-mdl2:office-store-logo",
  "Email, Calendar & Chat": "material-symbols:mark-email-unread-outline-rounded",
  "Commerce, CRM & Support": "material-symbols:storefront-outline-rounded",
  "Shipping, Payment & Accounting": "material-symbols:local-shipping-outline-rounded",
  "Data, DevOps & Internal Systems": "material-symbols:database-outline-rounded",
  "CellX Database": "material-symbols:database-outline-rounded",
  "AI Models": "material-symbols:neurology-outline-rounded",
  "Agent Skills & Tools": "material-symbols:account-tree-outline-rounded",
};

const appIcons = {
  "Order Created": "material-symbols:add-shopping-cart-rounded",
  "Payment Captured": "material-symbols:payments-outline-rounded",
  "Webhook Received": "material-symbols:webhook-rounded",
  "Schedule": "material-symbols:schedule-rounded",
  "If / Else Branch": "material-symbols:alt-route-rounded",
  "Switch / Match": "material-symbols:fork-right-rounded",
  "Filter Records": "material-symbols:filter-alt-outline-rounded",
  "Value Compare": "material-symbols:compare-arrows-rounded",
  "Loop Items": "material-symbols:repeat-rounded",
  "Wait / Delay": "material-symbols:timer-outline-rounded",
  "Stop Workflow": "material-symbols:stop-circle-outline-rounded",
  "Google Docs": "logos:google-docs",
  "Google Sheets": "logos:google-sheets",
  "Google Forms": "logos:google-forms",
  "Google Slides": "logos:google-slides",
  "Google Drive": "logos:google-drive",
  "Microsoft Word": "vscode-icons:file-type-word",
  "Microsoft Excel": "vscode-icons:file-type-excel",
  "OneDrive": "logos:microsoft-onedrive",
  "SharePoint": "logos:microsoft-sharepoint",
  "Box": "logos:box",
  "Dropbox": "logos:dropbox",
  "Notion": "logos:notion-icon",
  "Airtable": "logos:airtable",
  "Outlook Email": "logos:microsoft-outlook",
  "Outlook Calendar": "logos:microsoft-outlook",
  "Gmail": "logos:google-gmail",
  "Google Calendar": "logos:google-calendar",
  "Slack": "logos:slack-icon",
  "Microsoft Teams": "logos:microsoft-teams",
  "Discord": "logos:discord-icon",
  "Telegram Bot": "logos:telegram",
  "WhatsApp Business": "logos:whatsapp-icon",
  "Twilio SMS": "logos:twilio-icon",
  "Mailchimp": "logos:mailchimp-freddie",
  "LinkedIn": "logos:linkedin-icon",
  "Shopify": "logos:shopify",
  "WooCommerce": "logos:woocommerce-icon",
  "Magento": "logos:magento",
  "Walmart Marketplace": "simple-icons:walmart",
  "Amazon SP-API": "logos:aws",
  "eBay": "logos:ebay",
  "HubSpot": "logos:hubspot",
  "Salesforce": "logos:salesforce",
  "Pipedrive": "simple-icons:pipedrive",
  "Zoho CRM": "simple-icons:zoho",
  "Zendesk": "logos:zendesk-icon",
  "Intercom": "logos:intercom-icon",
  "Freshdesk": "simple-icons:freshworks",
  "FedEx": "simple-icons:fedex",
  "UPS": "simple-icons:ups",
  "USPS": "simple-icons:usps",
  "DHL": "logos:dhl",
  "Stripe": "logos:stripe",
  "PayPal": "logos:paypal",
  "Square": "logos:square",
  "QuickBooks": "simple-icons:intuit",
  "Xero": "logos:xero",
  "MySQL": "logos:mysql-icon",
  "PostgreSQL": "logos:postgresql",
  "MongoDB": "logos:mongodb-icon",
  "Redis": "logos:redis",
  "GitHub": "logos:github-icon",
  "GitLab": "logos:gitlab",
  "Jira": "logos:jira",
  "AWS Lambda": "logos:aws-lambda",
  "CellX Query Table": "material-symbols:table-view-outline-rounded",
  "CellX Get Detail": "material-symbols:pageview-outline-rounded",
  "CellX Insert Row": "material-symbols:add-row-below-rounded",
  "CellX Update Row": "material-symbols:edit-square-outline-rounded",
  "CellX Delete Row": "material-symbols:delete-outline-rounded",
  "CellX Upsert Row": "material-symbols:merge-type-rounded",
  "CellX Bulk Import": "material-symbols:upload-file-outline-rounded",
  "CellX Export Excel": "vscode-icons:file-type-excel",
  "Order Table: cx_order": "material-symbols:orders-outline-rounded",
  "Order Management: cx_orders_management": "material-symbols:receipt-long-outline-rounded",
  "Page Config: gen_table": "material-symbols:dynamic-form-outline-rounded",
  "Field Config: gen_table_column": "material-symbols:view-column-outline-rounded",
  "Workflow Log: cx_workflow_log": "material-symbols:history-rounded",
  "OpenAI GPT-5.6": "logos:openai-icon",
  "OpenAI GPT-5": "logos:openai-icon",
  "OpenAI GPT-5 mini": "logos:openai-icon",
  "Claude Sonnet 5": "simple-icons:anthropic",
  "Claude Opus 5": "simple-icons:anthropic",
  "Google Gemini": "logos:google-gemini",
  "DeepSeek": "simple-icons:deepseek",
  "Mistral": "simple-icons:mistralai",
  "Llama": "simple-icons:meta",
  "Perplexity": "simple-icons:perplexity",
  "Ollama Local Model": "simple-icons:ollama",
  "External Agent": "material-symbols:hub-outline-rounded",
  "GitHub External Agent": "mdi:github",
  "HTTP Request": "material-symbols:http-rounded",
  "Custom Script / Program": "material-symbols:terminal-rounded",
  "Webhook Reply": "material-symbols:reply-all-rounded",
  "SQL Query": "material-symbols:database-outline-rounded",
  "JSON Transform": "vscode-icons:file-type-json",
  "Excel Import Parser": "vscode-icons:file-type-excel",
  "PDF / Invoice Reader": "vscode-icons:file-type-pdf2",
  "Human Approval": "material-symbols:approval-delegation-outline-rounded",
  "Retry / Error Handler": "material-symbols:sync-problem-rounded",
};

function iconMarkup(icon, label, className = "node-icon") {
  if (!icon) return `<span class="${className} fallback">${label.slice(0, 1)}</span>`;
  const src = `https://api.iconify.design/${icon}.svg`;
  return `<img class="${className}" src="${src}" alt="" loading="lazy" onerror="this.replaceWith(Object.assign(document.createElement('span'),{className:'${className} fallback',textContent:'${label.slice(0, 1)}'}))">`;
}

function stripSensitiveSettings(settings = {}) {
  return Object.fromEntries(
    Object.entries(settings).filter(([key]) => !sensitiveSettingPattern.test(key))
  );
}

function isEmailNode(node) {
  const action = String(node?.action || "");
  const name = String(node?.name || "");
  return name === "Gmail" || name === "Outlook Email" || action.includes("/gmail/send") || action.includes("/mail");
}

function appendEmailRecipient(value, recipient = defaultEmailRecipient) {
  const parts = String(value || "")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
  if (!parts.some((item) => item.toLowerCase() === recipient.toLowerCase())) {
    parts.push(recipient);
  }
  return parts.join(",");
}

function nodeConfigSignature(workflowName, node) {
  return [workflowName || "Untitled Workflow", node?.type || "", node?.name || "", node?.action || ""]
    .map((part) => String(part).trim().toLowerCase().replace(/\s+/g, " "))
    .join("::");
}

function readNodeConfigStore() {
  try {
    return JSON.parse(localStorage.getItem(nodeConfigStoreKey) || "{}");
  } catch {
    return {};
  }
}

function writeNodeConfigStore(store) {
  localStorage.setItem(nodeConfigStoreKey, JSON.stringify(store));
}

function persistNodeConfig(node) {
  if (!node) return;
  const store = readNodeConfigStore();
  const signature = nodeConfigSignature(workflowTitle, node);
  store[signature] = {
    savedAt: new Date().toISOString(),
    workflowName: workflowTitle,
    nodeName: node.name,
    nodeType: node.type,
    action: node.action,
    integrationSettings: { ...(node.integrationSettings || {}) },
  };
  writeNodeConfigStore(store);
}

function applySavedNodeConfigs() {
  const store = readNodeConfigStore();
  nodes = nodes.map((node) => {
    const saved = store[nodeConfigSignature(workflowTitle, node)];
    if (!saved?.integrationSettings) return node;
    const integrationSettings = {
      ...(node.integrationSettings || {}),
      ...saved.integrationSettings,
    };
    if (node.type === "trigger" && node.action === "cron") {
      // A draft's schedule wins over the legacy cache shared by same-name templates.
      for (const key of ["schedule", "scheduleEnabled", "timezone"]) {
        if (Object.prototype.hasOwnProperty.call(node.integrationSettings || {}, key)) {
          integrationSettings[key] = node.integrationSettings[key];
        }
      }
    }
    if (isEmailNode(node)) {
      integrationSettings.to = appendEmailRecipient(integrationSettings.to);
    }
    // Uploaded assets belong to the draft, not the shared same-name config cache.
    delete integrationSettings.photoFilesJson;
    if (node.integrationSettings?.photoFilesJson) integrationSettings.photoFilesJson = node.integrationSettings.photoFilesJson;
    return { ...node, integrationSettings };
  });
}

function safeWorkflowNodes(sourceNodes = [], stripSecrets = true) {
  return sourceNodes.map((node) => {
    const integrationSettings = { ...(node.integrationSettings || {}) };
    if (isEmailNode(node)) {
      integrationSettings.to = appendEmailRecipient(integrationSettings.to);
    }
    return {
      id: String(node.id || ""),
      type: String(node.type || "action"),
      name: String(node.name || "Workflow Step"),
      action: String(node.action || ""),
      notes: String(node.notes || ""),
      icon: node.icon ? String(node.icon) : null,
      x: Number.isFinite(Number(node.x)) ? Number(node.x) : 80,
      y: Number.isFinite(Number(node.y)) ? Number(node.y) : 80,
      integrationSettings: stripSecrets ? stripSensitiveSettings(integrationSettings) : integrationSettings,
      connection: node.connection ? { ...node.connection } : null,
      testResult: node.testResult ? { ...node.testResult } : null,
    };
  });
}

function buildWorkflowTemplate() {
  return {
    templateType: "cellx-workflow-designer",
    version: templateVersion,
    exportedAt: new Date().toISOString(),
    name: workflowTitle || "CellX Workflow Template",
    description: workflowDescription || "",
    nodes: safeWorkflowNodes(nodes),
    links: links.map((link) => ({ from: String(link.from || ""), to: String(link.to || "") })),
  };
}

function workflowSnapshot(stripSecrets = false) {
  return {
    id: activeWorkflowId || `workflow-${Date.now()}`,
    name: workflowTitle || "Untitled Workflow",
    description: workflowDescription || "Drag nodes, reposition them, then connect steps.",
    nodes: safeWorkflowNodes(nodes, stripSecrets),
    links: links.map((link) => ({ from: String(link.from || ""), to: String(link.to || "") })),
  };
}

function syncActiveWorkflow() {
  if (!activeWorkflowId) return;
  const index = workflows.findIndex((workflow) => workflow.id === activeWorkflowId);
  const snapshot = workflowSnapshot(false);
  if (index >= 0) {
    workflows[index] = { ...workflows[index], ...snapshot };
  }
}

function saveWorkflowDraft(message = "") {
  persistWorkflowStore();
  return message || "Configuration saved in this browser.";
}

const workflowScheduleStatuses = new Map();

function dailyTrigger() {
  return nodes.find(node => node.type === "trigger" && node.action === "cron");
}

function serverWorkflowSnapshot() {
  const snapshot = workflowSnapshot(false);
  snapshot.nodes.forEach(node => {
    delete node.testResult;
    delete node.connection;
  });
  return snapshot;
}

async function saveActiveSchedule() {
  const trigger = dailyTrigger();
  if (!trigger) return "";
  const timeInput = propIntegration?.querySelector("[data-daily-run-time]");
  if (timeInput?.dataset.edited === "true" && !timeInput.checkValidity()) {
    timeInput.reportValidity();
    throw new Error("Choose a valid daily run time.");
  }
  if (typeof trigger.integrationSettings?.schedule === "string" && !trigger.integrationSettings.schedule.trim()) {
    throw new Error("Choose a daily run time or enter a cron expression.");
  }
  ensureIntegrationSettings(trigger);
  persistWorkflowStore();
  const workflowId = activeWorkflowId;
  const data = await workflowManagementFetch("/workflow-schedules/save", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ workflow: serverWorkflowSnapshot() }),
  });
  workflowScheduleStatuses.set(workflowId, data);
  if (activeWorkflowId === workflowId && selectedId === trigger.id) renderIntegrationFields(trigger);
  if (!data.scheduler?.running && data.schedule.enabled) throw new Error("Schedule saved, but the backend scheduler is offline.");
  return data.schedule.enabled
    ? uiMessage("Daily schedule saved on server. Next run: {date} ({timezone}).", { date: new Date(data.schedule.nextRun).toLocaleString("en-US", { timeZone: data.schedule.timezone }), timezone: data.schedule.timezone }, { date: [data.schedule.nextRun, { timeZone: data.schedule.timezone }] })
    : "Agent saved on server. Daily schedule is disabled.";
}

function scheduleStatusMarkup() {
  const data = workflowScheduleStatuses.get(activeWorkflowId);
  const schedule = data?.schedule;
  const nextRun = schedule?.nextRun ? `${uiDateMarkup(schedule.nextRun, { timeZone: schedule.timezone })} (${escapeHtml(schedule.timezone)})` : uiLabel("None");
  return `<section class="schedule-status"><button type="button" id="refreshScheduleBtn" ${uiAttrs("Schedule Status")}>${escapeHtml(agentT("Schedule Status"))}</button>
    ${schedule ? `<p>${uiLabel(schedule.saved ? schedule.enabled ? "Enabled" : "Disabled" : "Not saved on server")} | ${uiLabel("Scheduler:")} ${uiLabel(data.scheduler?.running ? "Running" : "Offline")}</p><p>${uiLabel("Next run:")} ${nextRun}</p>
      ${(schedule.runs || []).map(run => `<details><summary>${uiDateMarkup(run.started_at)} | ${escapeHtml(run.source)} | ${uiLabel(run.status)}</summary>
        ${(run.steps || []).map(step => `<p>${escapeHtml(step.name)}: ${uiLabel(step.status)}${step.row_count != null ? uiLabel(" ({count} rows)", { count: Number(step.row_count) }) : ""}</p>`).join("")}</details>`).join("")}` : ""}
  </section>`;
}

function persistWorkflowStore() {
  syncActiveWorkflow();
  localStorage.setItem(workflowStoreKey, JSON.stringify({
    version: templateVersion,
    activeWorkflowId,
    workflows,
  }));
}

function uniqueWorkflowId() {
  return `workflow-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
}

function migrateOrderDeskOrderViewer(workflow) {
  const nodesList = Array.isArray(workflow?.nodes) ? workflow.nodes : [];
  const hasOrderDeskFetch = nodesList.some((node) => node?.integrationSettings?.scriptName === "orderdesk_orders_to_db.py");
  const hasViewer = nodesList.some((node) => node?.name === "View CellX Orders" || node?.id === "node-view-cellx-orders");
  if (!hasOrderDeskFetch || hasViewer) return workflow;

  const importNode = nodesList.find((node) => node?.name === "CellX Bulk Import Orders" || node?.integrationSettings?.tableName === "cx_orderdesk_order");
  const viewerNode = {
    id: "node-view-cellx-orders",
    type: "cellx-db",
    name: "View CellX Orders",
    action: "/ext-api/cellx-db/query",
    notes: "Read the latest 500 OrderDesk order rows currently stored in CellX after the import finishes.",
    icon: "material-symbols:table-rows-outline-rounded",
    x: Number(importNode?.x || 650) + 290,
    y: Math.max(90, Number(importNode?.y || 160) - 40),
    integrationSettings: {
      operation: "query",
      tableName: "cx_orderdesk_order",
      whereClause: "del_flag = '0'",
      sortBy: "order_date desc, updated_date desc, id desc",
      limit: "500",
    },
    connection: null,
    testResult: null,
  };
  const linksList = Array.isArray(workflow?.links) ? workflow.links : [];
  const nextLinks = [...linksList];
  if (importNode?.id && !nextLinks.some((link) => link.from === importNode.id && link.to === viewerNode.id)) {
    nextLinks.push({ from: importNode.id, to: viewerNode.id });
  }
  return {
    ...workflow,
    nodes: [...nodesList, viewerNode],
    links: nextLinks,
  };
}

function normalizeWorkflow(draft, fallbackName = "Untitled Workflow", stripSecrets = true) {
  const valid = validateWorkflowTemplate({
    name: draft?.name || fallbackName,
    description: draft?.description || draft?.workflowDescription || "Drag nodes, reposition them, then connect steps.",
    nodes: Array.isArray(draft?.nodes) ? draft.nodes : [],
    links: Array.isArray(draft?.links) ? draft.links : [],
  }, stripSecrets);
  return {
    id: String(draft?.id || uniqueWorkflowId()),
    name: valid.name,
    description: valid.description,
    nodes: valid.nodes,
    links: valid.links,
  };
  return migrateOrderDeskOrderViewer(workflow);
}

function loadWorkflow(workflowId) {
  const workflow = workflows.find((item) => item.id === workflowId) || workflows[0];
  if (!workflow) return;
  activeWorkflowId = workflow.id;
  workflowTitle = workflow.name || "Untitled Workflow";
  workflowDescription = workflow.description || "Drag nodes, reposition them, then connect steps.";
  nodes = safeWorkflowNodes(workflow.nodes || [], false);
  links = (workflow.links || []).map((link) => ({ from: String(link.from), to: String(link.to) }));
  applySavedNodeConfigs();
  selectedId = nodes[0]?.id || null;
  activeResultNodeId = selectedId;
  connectFrom = null;
  connectMode = false;
  connectBtn.classList.remove("active");
  nextId = nextIdFromNodes(nodes);
  fitNodesToCanvas();
  render();
  renderWorkflowTabs();
  if (selectedId) {
    selectNode(selectedId);
  } else {
    clearProperties();
  }
}

function switchWorkflow(workflowId) {
  if (workflowId === activeWorkflowId) return;
  syncActiveWorkflow();
  loadWorkflow(workflowId);
  persistWorkflowStore();
}

function addWorkflowFromTemplate(template, makeActive = true) {
  const workflow = normalizeWorkflow(template, template?.name || "New Workflow");
  workflows.push(workflow);
  if (makeActive) {
    loadWorkflow(workflow.id);
  } else {
    renderWorkflowTabs();
  }
  persistWorkflowStore();
  return workflow;
}

function seedStarterWorkflow() {
  workflowTitle = "Order Fulfillment Flow";
  workflowDescription = "Drag nodes, reposition them, then connect steps.";
  nodes = [];
  links = [];
  nextId = 1;
  const starterPositions = autoLayoutPositions();
  addNode("trigger", ...starterPositions[0]);
  addNode("condition", ...starterPositions[1]);
  addNode("ai", ...starterPositions[2]);
  addNode("carrier", ...starterPositions[3]);
  addNode("action", ...starterPositions[4]);
  addNode("log", ...starterPositions[5]);
  links = [
    { from: "node-1", to: "node-2" },
    { from: "node-2", to: "node-3" },
    { from: "node-2", to: "node-4" },
    { from: "node-3", to: "node-5" },
    { from: "node-4", to: "node-5" },
    { from: "node-5", to: "node-6" },
  ];
  return workflowSnapshot(false);
}

function createBlankWorkflow(name = "Untitled Workflow") {
  return {
    id: uniqueWorkflowId(),
    name,
    description: "Drag nodes, reposition them, then connect steps.",
    nodes: [],
    links: [],
  };
}

function renderWorkflowTabs() {
  if (!workflowTabsEl) return;
  workflowTabsEl.innerHTML = workflows.map((workflow) => `
    <button class="workflow-tab${workflow.id === activeWorkflowId ? " active" : ""}" type="button" data-workflow-id="${escapeHtml(workflow.id)}" title="${escapeHtml(workflow.name || "Untitled Workflow")}">
      <span class="workflow-tab-title">${escapeHtml(workflow.name || "Untitled Workflow")}</span>
      <span class="workflow-tab-close" data-close-workflow-id="${escapeHtml(workflow.id)}" data-agent-i18n-attributes data-i18n-title="Close workflow" title="${escapeHtml(agentT("Close workflow"))}">×</span>
    </button>
  `).join("");
}

function nextIdFromNodes(items) {
  return items.reduce((max, node) => {
    const match = String(node.id || "").match(/^node-(\d+)$/);
    return Math.max(max, match ? Number(match[1]) + 1 : max);
  }, 1);
}

function validateWorkflowTemplate(template, stripSecrets = true) {
  if (!template || typeof template !== "object") {
    throw new Error("This file is not a workflow template.");
  }
  if (!Array.isArray(template.nodes) || !Array.isArray(template.links)) {
    throw new Error("Template must contain nodes and links arrays.");
  }
  const ids = new Set();
  for (const node of template.nodes) {
    if (!node.id || ids.has(node.id)) throw new Error("Template contains missing or duplicate node IDs.");
    ids.add(String(node.id));
  }
  const validLinks = template.links.filter((link) => ids.has(String(link.from)) && ids.has(String(link.to)));
  return {
    name: String(template.name || "Imported Workflow"),
    description: String(template.description || "Drag nodes, reposition them, then connect steps."),
    nodes: safeWorkflowNodes(template.nodes, stripSecrets),
    links: validLinks.map((link) => ({ from: String(link.from), to: String(link.to) })),
  };
}

function applyWorkflowTemplate(template, useSavedConfigs = true) {
  const draft = validateWorkflowTemplate(template);
  workflowTitle = draft.name;
  workflowDescription = draft.description;
  nodes = draft.nodes;
  links = draft.links;
  if (useSavedConfigs) applySavedNodeConfigs();
  selectedId = nodes[0]?.id || null;
  activeResultNodeId = selectedId;
  connectFrom = null;
  connectMode = false;
  connectBtn.classList.remove("active");
  nextId = nextIdFromNodes(nodes);
  fitNodesToCanvas();
  persistWorkflowStore();
  render();
  if (selectedId) {
    selectNode(selectedId);
  } else {
    propName.value = "";
    propType.value = "";
    propAction.value = "";
    propNotes.value = "";
    propIntegration.innerHTML = "";
  }
}

function downloadWorkflowTemplate() {
  const template = buildWorkflowTemplate();
  const data = JSON.stringify(template, null, 2);
  const date = new Date().toISOString().slice(0, 10);
  const blob = new Blob([data], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `cellx-workflow-template-${date}.json`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function importWorkflowTemplate(file) {
  if (!file) return;
  const reader = new FileReader();
  reader.addEventListener("load", () => {
    try {
      addWorkflowFromTemplate(JSON.parse(String(reader.result || "{}")), true);
      alert(agentT("Workflow template imported as a new tab."));
    } catch (error) {
      alert(agentT(error.message || "Could not import this workflow template."));
    }
  });
  reader.addEventListener("error", () => {
    alert(agentT("Could not read this template file."));
  });
  reader.readAsText(file);
}

async function loadTemplateLibrary(force = false) {
  if (templateLibrary.length && !force) return templateLibrary;
  if (templateLibraryStatusEl) uiText(templateLibraryStatusEl, "Loading templates...");
  try {
    const response = await fetch(`${templateManifestPath}?v=${Date.now()}`, { cache: "no-store" });
    if (!response.ok) throw new Error(uiMessage("Template manifest returned {status}", { status: response.status }));
    const manifest = await response.json();
    templateLibrary = Array.isArray(manifest.templates) ? manifest.templates : [];
    if (templateLibraryStatusEl) {
      uiText(templateLibraryStatusEl, templateLibrary.length === 1 ? "{count} template available" : "{count} templates available", { count: templateLibrary.length });
    }
    renderTemplateCategoryFilter();
  } catch (error) {
    templateLibrary = [];
    if (templateLibraryStatusEl) uiText(templateLibraryStatusEl, "Template library unavailable");
    console.warn("Could not load workflow template library", error);
    renderTemplateCategoryFilter();
  }
  renderTemplateLibrary();
  return templateLibrary;
}

function templateCategoryClass(category) {
  const slug = String(category || "workflow")
    .toLowerCase()
    .replace(/&/g, "and")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "") || "workflow";
  return `template-category-${slug}`;
}

function renderTemplateCategoryFilter() {
  if (!templateCategoryFilterEl) return;
  const previous = templateCategoryFilterEl.value;
  const categories = Array.from(new Set(templateLibrary.map((template) => template.category || "Workflow"))).sort();
  templateCategoryFilterEl.innerHTML = [
    `<option value="" ${uiAttrs("All categories")}>${escapeHtml(agentT("All categories"))}</option>`,
    ...categories.map((category) => `<option value="${escapeHtml(category)}">${escapeHtml(category)}</option>`),
  ].join("");
  if (categories.includes(previous)) {
    templateCategoryFilterEl.value = previous;
  }
}

function renderTemplateLibrary() {
  if (!templateListEl) return;
  const query = String(templateSearchEl?.value || "").trim().toLowerCase();
  const categoryFilter = String(templateCategoryFilterEl?.value || "").trim();
  const filtered = templateLibrary.filter((template) => {
    const haystack = [
      template.name,
      template.description,
      template.category,
      template.demoUse,
      ...(Array.isArray(template.tags) ? template.tags : []),
    ].join(" ").toLowerCase();
    const matchesCategory = !categoryFilter || (template.category || "Workflow") === categoryFilter;
    const matchesQuery = !query || haystack.includes(query);
    return matchesCategory && matchesQuery;
  });
  if (!filtered.length) {
    templateListEl.innerHTML = `<div class="template-empty" ${uiAttrs("No templates found.")}>${escapeHtml(agentT("No templates found."))}</div>`;
    return;
  }
  templateListEl.innerHTML = filtered.map((template) => `
    <article class="template-card ${escapeHtml(templateCategoryClass(template.category))}">
      <div class="template-card-main">
        <div class="template-card-top">
          <span class="template-category">${escapeHtml(template.category || "Workflow")}</span>
          <span class="template-file">${escapeHtml(template.file || "")}</span>
        </div>
        <h2>${template.name ? escapeHtml(template.name) : uiLabel("Workflow Template")}</h2>
        <p>${template.description ? escapeHtml(template.description) : uiLabel("Generated workflow JSON template.")}</p>
        <div class="template-tags">
          ${(Array.isArray(template.tags) ? template.tags : []).map((tag) => `<span>${escapeHtml(tag)}</span>`).join("")}
        </div>
      </div>
      <div class="template-card-actions">
        <button type="button" data-preview-template="${escapeHtml(template.file || "")}" ${uiAttrs("Preview JSON")}>${escapeHtml(agentT("Preview JSON"))}</button>
        <button class="primary" type="button" data-import-library-template="${escapeHtml(template.file || "")}" ${uiAttrs("Import")}>${escapeHtml(agentT("Import"))}</button>
      </div>
    </article>
  `).join("");
}

async function fetchLibraryTemplate(template) {
  if (!template?.file) throw new Error("Template file is missing.");
  const response = await fetch(`./workflow-templates/${encodeURIComponent(template.file)}?v=${Date.now()}`, { cache: "no-store" });
  if (!response.ok) throw new Error(uiMessage("Could not load {name}.", { name: template.file }));
  return response.json();
}

async function importLibraryTemplate(template) {
  try {
    const workflow = addWorkflowFromTemplate(await fetchLibraryTemplate(template), true);
    alert(agentT("Imported \"{name}\" as a new workflow tab.", { name: workflow.name }));
    if (templateBrowser) templateBrowser.hidden = true;
  } catch (error) {
    alert(agentT(error.message || "Could not import this template."));
  }
}

async function previewLibraryTemplate(template) {
  try {
    const data = await fetchLibraryTemplate(template);
    const preview = JSON.stringify(data, null, 2);
    const win = window.open("", "_blank", "width=920,height=720");
    if (!win) {
      alert(preview.slice(0, 4000));
      return;
    }
    win.document.write(`<pre style="white-space:pre-wrap;font:13px/1.45 Consolas,monospace;padding:18px;color:#14213d;">${escapeHtml(preview)}</pre>`);
    win.document.title = data.name || template.name || "Workflow Template JSON";
  } catch (error) {
    alert(agentT(error.message || "Could not preview this template."));
  }
}

function setAiVoiceStatus(message, params = {}) {
  uiText(aiVoiceStatusEl, message, params);
}

function setAiWorkflowDraft(template) {
  aiWorkflowDraft = template;
  if (aiVoiceDraftPreviewEl) aiVoiceDraftPreviewEl.textContent = template ? JSON.stringify(template, null, 2) : "{}";
  if (aiVoiceDraftMetaEl) {
    uiText(aiVoiceDraftMetaEl, template ? "{nodes} nodes, {links} links" : "No draft yet", { nodes: template?.nodes?.length || 0, links: template?.links?.length || 0 });
  }
  if (importAiDraftBtn) importAiDraftBtn.disabled = !template;
}

let realtimeVoice = null;
let aiDraftTarget = null;
let aiDraftBaseline = null;
let aiBuildVersion = 0;

function aiVoiceHeaders() {
  return { "Content-Type": "application/json", "X-Workflow-Admin-Token":
    document.getElementById("aiVoiceAccessToken")?.value || sessionStorage.getItem("cellx-workflow-management-token") || "" };
}

// Workflow settings can contain JSON strings with nested credentials.
function aiSafeContext(value, key = "") {
  if (/api.?key|secret|password|token|authorization|authheader|testresult|connection/i.test(key)) return undefined;
  if (Array.isArray(value)) return value.map((item) => aiSafeContext(item));
  if (value && typeof value === "object") return Object.fromEntries(Object.entries(value)
    .map(([name, item]) => [name, aiSafeContext(item, name)]).filter(([, item]) => item !== undefined));
  if (typeof value === "string") {
    try { const parsed = JSON.parse(value); if (parsed && typeof parsed === "object") return JSON.stringify(aiSafeContext(parsed)); } catch { /* Plain text setting. */ }
  }
  return value;
}

function voiceLine(role, text) {
  if (!text) return;
  const log = document.getElementById("aiVoiceConversation");
  const line = document.createElement("p");
  const label = document.createElement("strong");
  label.innerHTML = uiLabel(role) + ": ";
  line.append(label, document.createTextNode(text));
  log.append(line);
  while (log.childElementCount > 80) log.firstElementChild.remove();
  log.scrollTop = log.scrollHeight;
}

function voiceControls(connected, connecting = false) {
  document.getElementById("voiceListenBtn").disabled = connected || connecting;
  document.getElementById("voiceStopBtn").disabled = !connected && !connecting;
  document.getElementById("voiceMuteBtn").disabled = !connected;
  document.getElementById("voiceSendBtn").disabled = !connected;
  window.VoiceScreenshots?.render();
}

function voiceSend(session, event) {
  if (realtimeVoice === session && session.channel?.readyState === "open") {
    session.channel.send(JSON.stringify(event));
  }
}

async function createVoiceWorkflowDraft(request, mode, session = null) {
  const version = ++aiBuildVersion;
  const target = mode === "update" ? activeWorkflowId : null;
  const baseline = JSON.stringify(workflowSnapshot(true));
  const usePending = mode === "update" && aiWorkflowDraft &&
    (aiDraftTarget === null || (aiDraftTarget === target && aiDraftBaseline === baseline));
  const draftTarget = usePending ? aiDraftTarget : target;
  const draftBaseline = usePending ? aiDraftBaseline : baseline;
  const current = mode === "update" ? (usePending ? aiWorkflowDraft : workflowSnapshot(true)) : {};
  setAiVoiceStatus("Building workflow draft...");
  const response = await fetch(`${apiBase}/ai/workflow-builder`, {
    method: "POST", headers: aiVoiceHeaders(),
    body: JSON.stringify({ prompt: request, currentWorkflow: aiSafeContext(current), availableNodes: nodeCatalog,
      screenshots: window.VoiceScreenshots?.images() || [] }),
    signal: session?.abort.signal || AbortSignal.timeout(90000),
  });
  const data = await response.json();
  if (!response.ok || !data.ok) throw new Error(data.message || "Could not build workflow.");
  if (version !== aiBuildVersion || (session && realtimeVoice !== session)) throw new Error("Draft request cancelled.");
  const draft = validateWorkflowTemplate(data.template);
  aiDraftTarget = draftTarget;
  aiDraftBaseline = draftBaseline;
  setAiWorkflowDraft(draft);
  setAiVoiceStatus("Draft ready. Apply when ready.");
  return { ok: true, name: draft.name, nodes: draft.nodes.length, applied: false };
}

function retainVoiceCredentials(original, draft) {
  if (typeof original === "string" && typeof draft === "string") {
    try {
      const before = JSON.parse(original), after = JSON.parse(draft);
      if (before && after && typeof before === "object" && typeof after === "object") return JSON.stringify(retainVoiceCredentials(before, after));
    } catch { /* Non-JSON settings use the draft value. */ }
  }
  if (original && draft && typeof original === "object" && typeof draft === "object" && !Array.isArray(original) && !Array.isArray(draft)) {
    const merged = { ...draft };
    for (const [key, value] of Object.entries(original)) {
      if (/api.?key|secret|password|token|authorization|authheader/i.test(key)) merged[key] = value;
      else if (key in draft) merged[key] = retainVoiceCredentials(value, draft[key]);
    }
    return merged;
  }
  return draft;
}

function applyVoiceWorkflowDraft() {
  if (!aiWorkflowDraft) throw new Error("No pending draft. Create a draft first.");
  let workflow;
  if (aiDraftTarget) {
    if (activeWorkflowId !== aiDraftTarget || JSON.stringify(workflowSnapshot(true)) !== aiDraftBaseline) {
      throw new Error("The active workflow changed. Build a fresh draft before applying.");
    }
    const localSettings = new Map(nodes.map(node => [node.id, node]));
    applyWorkflowTemplate(aiWorkflowDraft, false);
    nodes = nodes.map(node => {
      const previous = localSettings.get(node.id);
      if (previous?.type !== node.type || previous?.action !== node.action) return node;
      return { ...node, integrationSettings: retainVoiceCredentials(previous.integrationSettings, node.integrationSettings) };
    });
    nodes.forEach(persistNodeConfig);
    persistWorkflowStore();
    render();
    if (selectedId) selectNode(selectedId);
    workflow = workflowSnapshot(true);
  } else {
    workflow = addWorkflowFromTemplate(aiWorkflowDraft, true);
  }
  setAiWorkflowDraft(null);
  aiBuildVersion++;
  aiDraftTarget = null;
  aiDraftBaseline = null;
  setAiVoiceStatus("Applied {name}. Not executed.", { name: workflow.name });
  return { ok: true, name: workflow.name, applied: true, executed: false };
}

async function handleVoiceEvent(session, event) {
  if (realtimeVoice !== session) return;
  if (event.type === "conversation.item.input_audio_transcription.completed") voiceLine("You", event.transcript);
  if (event.type === "response.output_audio_transcript.done") voiceLine("AI", event.transcript);
  if (event.type === "error") setAiVoiceStatus(event.error?.message || "Voice request failed.");
  if (event.type === "response.done" && event.response?.status === "failed") setAiVoiceStatus("Voice response failed. Check account access and retry.");
  if (event.type !== "response.function_call_arguments.done" || session.calls.has(event.call_id)) return;
  session.calls.add(event.call_id);
  let output;
  try {
    const args = JSON.parse(event.arguments || "{}");
    if (event.name === "get_current_workflow") output = aiSafeContext(workflowSnapshot(true));
    else if (event.name === "build_workflow") {
      if (!args.request || !["create", "update"].includes(args.mode)) throw new Error("Missing workflow request or mode.");
      output = await createVoiceWorkflowDraft(args.request, args.mode, session);
    } else if (event.name === "apply_workflow_draft") output = applyVoiceWorkflowDraft();
    else throw new Error("Unsupported workflow operation.");
  } catch (error) {
    output = { ok: false, message: error.message };
    if (realtimeVoice === session) setAiVoiceStatus(error.message);
  }
  voiceSend(session, { type: "conversation.item.create", item: {
    type: "function_call_output", call_id: event.call_id, output: JSON.stringify(output),
  } });
  voiceSend(session, { type: "response.create" });
}

async function startVoiceWorkflowCapture() {
  if (realtimeVoice) return;
  if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia || !window.RTCPeerConnection) {
    setAiVoiceStatus("Voice needs HTTPS or localhost and a browser with microphone support.");
    return;
  }
  const session = { abort: new AbortController(), calls: new Set(), pc: null, stream: null, channel: null };
  realtimeVoice = session;
  voiceControls(false, true);
  setAiVoiceStatus("Connecting voice...");
  session.timer = setTimeout(() => {
    if (realtimeVoice === session) { stopVoiceWorkflowCapture(); setAiVoiceStatus("Voice connection timed out. Please retry."); }
  }, 45000);
  try {
    const response = await fetch(`${apiBase}/ai/realtime-session`, {
      method: "POST", headers: aiVoiceHeaders(), body: "{}", signal: session.abort.signal,
    });
    const token = await response.json();
    if (!response.ok || !token.ok) throw new Error(token.message || "Voice connection failed.");
    const stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } });
    if (realtimeVoice !== session) { stream.getTracks().forEach((track) => track.stop()); return; }
    session.stream = stream;
    const pc = session.pc = new RTCPeerConnection();
    stream.getTracks().forEach((track) => pc.addTrack(track, stream));
    const audio = document.getElementById("aiVoiceAudio");
    pc.ontrack = (event) => { audio.srcObject = event.streams[0]; audio.play().catch(() => setAiVoiceStatus("Allow audio playback to hear the assistant.")); };
    pc.onconnectionstatechange = () => {
      if (realtimeVoice === session && ["failed", "disconnected", "closed"].includes(pc.connectionState)) {
        stopVoiceWorkflowCapture(); setAiVoiceStatus("Voice disconnected. Reconnect to continue.");
      }
    };
    const channel = session.channel = pc.createDataChannel("oai-events");
    channel.onmessage = (message) => {
      try { handleVoiceEvent(session, JSON.parse(message.data)).catch(() => setAiVoiceStatus("Could not process voice event.")); } catch { /* Ignore non-JSON events. */ }
    };
    channel.onopen = () => {
      if (realtimeVoice !== session) return;
      clearTimeout(session.timer);
      voiceControls(true);
      setAiVoiceStatus("Voice connected.");
      voiceSend(session, { type: "response.create", response: { instructions: "Briefly greet the user and ask what workflow they want to create or change. Do not call tools yet." } });
    };
    channel.onclose = () => { if (realtimeVoice === session) stopVoiceWorkflowCapture(); };
    const offer = await pc.createOffer();
    await pc.setLocalDescription(offer);
    const answer = await fetch("https://api.openai.com/v1/realtime/calls", {
      method: "POST", headers: { Authorization: `Bearer ${token.value}`, "Content-Type": "application/sdp" },
      body: offer.sdp, signal: session.abort.signal,
    });
    if (!answer.ok) throw new Error(uiMessage("Voice session rejected (HTTP {status}).", { status: answer.status }));
    const sdp = await answer.text();
    if (realtimeVoice === session) await pc.setRemoteDescription({ type: "answer", sdp });
  } catch (error) {
    if (realtimeVoice === session) {
      stopVoiceWorkflowCapture();
      setAiVoiceStatus(error.name === "NotAllowedError" ? "Microphone permission denied. Allow it in browser settings." : error.message);
    }
  }
}

function stopVoiceWorkflowCapture() {
  const session = realtimeVoice;
  realtimeVoice = null;
  if (session) {
    clearTimeout(session.timer);
    session.abort.abort();
    session.stream?.getTracks().forEach((track) => track.stop());
    session.channel?.close();
    session.pc?.close();
  }
  const audio = document.getElementById("aiVoiceAudio");
  audio.pause();
  audio.srcObject = null;
  const mute = document.getElementById("voiceMuteBtn");
  mute.setAttribute("aria-pressed", "false");
  uiText(mute, "Mute");
  voiceControls(false);
  setAiVoiceStatus("Voice disconnected.");
}

async function buildWorkflowWithAi() {
  const prompt = String(aiVoicePromptEl?.value || "").trim();
  if (!prompt) {
    setAiVoiceStatus("Type or speak a workflow request first.");
    return;
  }
  try {
    await createVoiceWorkflowDraft(prompt, "update");
  } catch (error) {
    setAiVoiceStatus(error.message || "Could not build workflow.");
  }
}

function importAiWorkflowDraft() {
  try { applyVoiceWorkflowDraft(); } catch (error) { setAiVoiceStatus(error.message); }
}

function formatManagerBytes(value) {
  const size = Number(value || 0);
  if (size >= 1024 * 1024) return `${(size / 1024 / 1024).toFixed(1)} MB`;
  if (size >= 1024) return `${Math.round(size / 1024)} KB`;
  return `${size} B`;
}

function formatManagerDate(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return uiDate(value);
}

function workflowManagementToken(forcePrompt = false) {
  let token = sessionStorage.getItem(workflowManagementTokenStoreKey) || "";
  if (!token || forcePrompt) {
    token = window.prompt(agentT("Enter workflow management admin token")) || "";
    if (token) sessionStorage.setItem(workflowManagementTokenStoreKey, token);
  }
  return token;
}

async function workflowManagementFetch(path, options = {}) {
  const token = workflowManagementToken();
  if (!token) throw new Error("Workflow management token is required.");
  const response = await fetch(`${apiBase}${path}`, {
    ...options,
    headers: {
      ...(options.headers || {}),
      "X-Workflow-Admin-Token": token,
    },
  });
  const data = await response.json();
  if (response.status === 401) {
    sessionStorage.removeItem(workflowManagementTokenStoreKey);
    workflowManagementToken(true);
  }
  if (!response.ok || (!data.ok && !(path === "/workflows/run" && Array.isArray(data.results)))) throw new Error(data.message || "Workflow management request failed.");
  return data;
}

async function loadTemplateManager() {
  if (templateManagerStatusEl) uiText(templateManagerStatusEl, "Loading backend inventory...");
  try {
    const data = await workflowManagementFetch(`/workflow-management?v=${Date.now()}`, { cache: "no-store" });
    templateManagerState = data;
    renderTemplateManager();
    if (templateManagerStatusEl) {
      uiText(templateManagerStatusEl, "Backend: {templates} | {scripts}", { templates: data.templateDir || "templates", scripts: data.scriptDir || "scripts" });
    }
  } catch (error) {
    templateManagerState = { templates: [], scripts: [], timers: [] };
    renderTemplateManager();
    if (templateManagerStatusEl) uiText(templateManagerStatusEl, error.message || "Template manager unavailable");
  }
}

function renderTemplateManager() {
  const templates = Array.isArray(templateManagerState.templates) ? templateManagerState.templates : [];
  const scripts = Array.isArray(templateManagerState.scripts) ? templateManagerState.scripts : [];
  const timers = Array.isArray(templateManagerState.timers) ? templateManagerState.timers : [];

  if (managedTemplateCountEl) uiText(managedTemplateCountEl, templates.length === 1 ? "{count} file" : "{count} files", { count: templates.length });
  if (managedScriptCountEl) uiText(managedScriptCountEl, scripts.length === 1 ? "{count} file" : "{count} files", { count: scripts.length });
  if (managedTimerCountEl) uiText(managedTimerCountEl, timers.length === 1 ? "{count} job" : "{count} jobs", { count: timers.length });

  if (managedTemplateListEl) {
    managedTemplateListEl.innerHTML = templates.length ? templates.map((item) => `
      <article class="manager-item">
        <div>
          <strong>${escapeHtml(item.name || item.file)}</strong>
          <span>${escapeHtml(item.file)} · ${escapeHtml(item.category || "Workflow")} · ${formatManagerBytes(item.size)}</span>
          <small>${uiLabel(item.inManifest ? "Listed in manifest" : "File only")} · ${uiLabel("Modified")} ${uiDateMarkup(item.modifiedAt)}</small>
        </div>
        <button class="danger" type="button" data-delete-managed-template="${escapeHtml(item.file)}" ${uiAttrs("Delete")}>${escapeHtml(agentT("Delete"))}</button>
      </article>
    `).join("") : `<div class="template-empty" ${uiAttrs("No backend template files found.")}>${escapeHtml(agentT("No backend template files found."))}</div>`;
  }

  if (managedScriptListEl) {
    managedScriptListEl.innerHTML = scripts.length ? scripts.map((item) => `
      <article class="manager-item">
        <div>
          <strong>${escapeHtml(item.file)}</strong>
          <span>${formatManagerBytes(item.size)}</span>
          <small>${uiLabel("Modified")} ${uiDateMarkup(item.modifiedAt)}</small>
        </div>
        <button class="danger" type="button" data-delete-managed-script="${escapeHtml(item.file)}" ${uiAttrs("Delete")}>${escapeHtml(agentT("Delete"))}</button>
      </article>
    `).join("") : `<div class="template-empty" ${uiAttrs("No customer scripts found.")}>${escapeHtml(agentT("No customer scripts found."))}</div>`;
  }

  if (managedTimerListEl) {
    managedTimerListEl.innerHTML = timers.length ? timers.map((item) => {
      const enabled = item.enabled === "enabled";
      const active = item.active === "active";
      return `
        <article class="manager-item manager-timer">
          <div>
            <strong>${escapeHtml(item.label || item.name)}</strong>
            <span>${escapeHtml(item.name)} · ${uiLabel(item.enabled || "unknown")} · ${uiLabel(item.active || "unknown")}</span>
            <small>${item.scheduleLine || item.next ? escapeHtml(item.scheduleLine || item.next) : uiLabel("No next run found")}</small>
          </div>
          <div class="manager-actions">
            <button type="button" data-managed-timer-action="${enabled || active ? "disable" : "enable"}" data-managed-timer="${escapeHtml(item.name)}">${uiLabel(enabled || active ? "Disable" : "Enable")}</button>
            <button class="danger" type="button" data-managed-timer-action="delete" data-managed-timer="${escapeHtml(item.name)}" ${uiAttrs("Delete Timer")}>${escapeHtml(agentT("Delete Timer"))}</button>
          </div>
        </article>
      `;
    }).join("") : `<div class="template-empty" ${uiAttrs("No managed scheduled jobs found.")}>${escapeHtml(agentT("No managed scheduled jobs found."))}</div>`;
  }
}

async function deleteManagedTemplate(file) {
  const item = (templateManagerState.templates || []).find((entry) => entry.file === file);
  if (!file || !window.confirm(agentT("Delete backend template \"{name}\"?\n\nThis removes the JSON file from the server and updates the template manifest.", { name: item?.name || file }))) return;
  await workflowManagementFetch(`/workflow-management/templates/delete`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ file }),
  });
  templateLibrary = [];
  await loadTemplateManager();
  await loadTemplateLibrary(true);
}

async function deleteManagedScript(file) {
  if (!file || !window.confirm(agentT("Delete backend script \"{name}\"?\n\nIf a workflow or timer still references it, that run will fail.", { name: file }))) return;
  await workflowManagementFetch(`/workflow-management/scripts/delete`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ file }),
  });
  await loadTemplateManager();
}

async function manageTimer(timerName, action) {
  const label = action === "delete" ? "Are you sure you want to delete this timer file?" : action === "disable" ? "Are you sure you want to stop this daily schedule?" : "Are you sure you want to enable this daily schedule?";
  if (!timerName || !window.confirm(agentT(label))) return;
  await workflowManagementFetch(`/workflow-management/timers`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ timerName, action }),
  });
  await loadTemplateManager();
}

function localMarketplaceItems() {
  try {
    return JSON.parse(localStorage.getItem(marketplaceStoreKey) || "[]");
  } catch {
    return [];
  }
}

function saveLocalMarketplaceItem(item) {
  const items = localMarketplaceItems();
  items.unshift(item);
  localStorage.setItem(marketplaceStoreKey, JSON.stringify(items.slice(0, 100)));
}

function marketplaceItemKey(item) {
  return String(item?.id || item?.file || item?.name || "");
}

function deletedMarketplaceKeys() {
  try {
    return JSON.parse(localStorage.getItem(marketplaceDeletedStoreKey) || "[]");
  } catch {
    return [];
  }
}

function setDeletedMarketplaceKeys(keys) {
  localStorage.setItem(marketplaceDeletedStoreKey, JSON.stringify(Array.from(new Set(keys)).slice(0, 300)));
}

function visibleMarketplaceItems(items) {
  const deleted = new Set(deletedMarketplaceKeys());
  return items.filter((item) => {
    const keys = [marketplaceItemKey(item), item?.id, item?.file, item?.name].map((value) => String(value || ""));
    return !keys.some((key) => key && deleted.has(key));
  });
}

function hideMarketplaceItem(item) {
  const deleted = deletedMarketplaceKeys();
  [marketplaceItemKey(item), item?.id, item?.file, item?.name].forEach((key) => {
    if (key) deleted.push(String(key));
  });
  setDeletedMarketplaceKeys(deleted);
  marketplaceItems = visibleMarketplaceItems(marketplaceItems);
  renderMarketplaceCategoryFilter();
  renderMarketplace();
  if (marketplaceStatusEl) {
    uiText(marketplaceStatusEl, marketplaceItems.length === 1 ? "{count} marketplace template available" : "{count} marketplace templates available", { count: marketplaceItems.length });
  }
}

function marketplaceUser() {
  try {
    return JSON.parse(localStorage.getItem(marketplaceUserStoreKey) || localStorage.getItem("cell-ai-data-marketplace-user") || "null");
  } catch {
    return null;
  }
}

function setMarketplaceUser(user) {
  if (user) {
    localStorage.setItem(marketplaceUserStoreKey, JSON.stringify(user));
    localStorage.setItem("cell-ai-data-marketplace-user", JSON.stringify(user));
  }
  renderMarketplaceAccount();
}

function marketplaceToken() {
  return localStorage.getItem(marketplaceTokenStoreKey) || localStorage.getItem("cell-ai-data-marketplace-token") || "";
}

function setMarketplaceToken(token) {
  if (!token) return;
  localStorage.setItem(marketplaceTokenStoreKey, token);
  localStorage.setItem("cell-ai-data-marketplace-token", token);
}

function renderMarketplaceAccount() {
  const user = marketplaceUser();
  const developerEmail = document.getElementById("marketplaceDeveloperEmail");
  if (user && developerEmail && !developerEmail.value) developerEmail.value = user.email || "";
  if (!marketplaceAccountStatusEl) return;
  if (!user) {
    uiText(marketplaceAccountStatusEl, "Login or register before publishing and buying.");
    return;
  }
  const connectState = user.stripeConnectedAccountId ? "Stripe account linked" : "Stripe payout not linked";
  marketplaceAccountStatusEl.innerHTML = uiLabel("{name} signed in as {role}.", { name: user.name || user.email, role: user.role || "user" }) + " " + uiLabel(connectState) + ".";
  marketplaceAccountStatusEl.removeAttribute("data-agent-i18n");
  marketplaceAccountStatusEl.removeAttribute("data-i18n");
}

async function submitMarketplaceAuth(event) {
  event.preventDefault();
  const submitter = event.submitter;
  const mode = submitter?.dataset.marketplaceAuth || "login";
  const payload = {
    name: document.getElementById("marketplaceAccountName")?.value || "",
    email: document.getElementById("marketplaceAccountEmail")?.value || "",
    password: document.getElementById("marketplaceAccountPassword")?.value || "",
    role: document.getElementById("marketplaceAccountRole")?.value || "developer_member",
  };
  try {
    const response = await fetch(`${apiBase}/marketplace/${mode}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await response.json();
    if (!response.ok || !data.ok) throw new Error(data.message || "Marketplace account request failed.");
    setMarketplaceUser(data.user);
    setMarketplaceToken(data.sessionToken);
    alert(agentT("{status}: {email}", { status: agentT(mode === "register" ? "Registered" : "Logged in"), email: data.user.email }));
  } catch (error) {
    alert(agentT(error.message || "Marketplace account request failed."));
  }
}

async function connectStripePayout() {
  const user = marketplaceUser();
  const email = user?.email || document.getElementById("marketplaceAccountEmail")?.value || document.getElementById("marketplaceDeveloperEmail")?.value;
  if (!email) {
    alert(agentT("Enter or login with a developer email first."));
    return;
  }
  try {
    const response = await fetch(`${apiBase}/marketplace/developer/onboarding`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, marketplaceToken: marketplaceToken() }),
    });
    const data = await response.json();
    if (!response.ok || !data.ok) throw new Error(data.message || "Could not start Stripe onboarding.");
    if (data.user) setMarketplaceUser(data.user);
    if (data.onboardingUrl) {
      window.open(data.onboardingUrl, "_blank", "noopener");
    } else {
      alert(agentT(data.message || "Stripe Connect requires STRIPE_SECRET_KEY on the backend."));
    }
  } catch (error) {
    alert(agentT(error.message || "Could not start Stripe onboarding."));
  }
}

function marketplaceCategories() {
  return Array.from(new Set(marketplaceItems.map((item) => item.category || "Workflow"))).sort();
}

function renderMarketplaceCategoryFilter() {
  if (!marketplaceCategoryFilterEl) return;
  const previous = marketplaceCategoryFilterEl.value;
  const categories = marketplaceCategories();
  marketplaceCategoryFilterEl.innerHTML = [
    `<option value="" ${uiAttrs("All categories")}>${escapeHtml(agentT("All categories"))}</option>`,
    ...categories.map((category) => `<option value="${escapeHtml(category)}">${escapeHtml(category)}</option>`),
  ].join("");
  if (categories.includes(previous)) marketplaceCategoryFilterEl.value = previous;
}

function marketplaceSeedItems() {
  return templateLibrary.map((template, index) => {
    const price = index < 3 ? 49 : 19;
    return {
      id: `library-${template.file || index}`,
      name: template.name || "Workflow Template",
      description: template.description || "Reusable workflow template.",
      category: template.category || "Workflow",
      developerName: "Cell AI Data",
      price,
      currency: "USD",
      platformFee: Math.round(price * 25) / 100,
      developerShare: Math.round(price * 75) / 100,
      sales: 0,
      status: "listed",
      source: "library",
      file: template.file,
    };
  });
}

async function loadMarketplace(force = false) {
  if (marketplaceItems.length && !force) return marketplaceItems;
  if (marketplaceStatusEl) uiText(marketplaceStatusEl, "Loading marketplace...");
  await loadTemplateLibrary();
  let apiItems = [];
  try {
    const response = await fetch(`${apiBase}/marketplace/templates?v=${Date.now()}`, { cache: "no-store" });
    if (response.ok) {
      const data = await response.json();
      apiItems = Array.isArray(data.items) ? data.items : [];
    }
  } catch (error) {
    console.warn("Marketplace API unavailable, using local demo listings.", error);
  }
  marketplaceItems = visibleMarketplaceItems([...apiItems, ...localMarketplaceItems(), ...marketplaceSeedItems()]);
  renderMarketplaceCategoryFilter();
  renderMarketplace();
  if (marketplaceStatusEl) {
    uiText(marketplaceStatusEl, marketplaceItems.length === 1 ? "{count} marketplace template available" : "{count} marketplace templates available", { count: marketplaceItems.length });
  }
  return marketplaceItems;
}

function renderMarketplace() {
  if (!marketplaceListEl) return;
  const query = String(marketplaceSearchEl?.value || "").trim().toLowerCase();
  const category = String(marketplaceCategoryFilterEl?.value || "").trim();
  const filtered = marketplaceItems.filter((item) => {
    const haystack = [item.name, item.description, item.category, item.developerName].join(" ").toLowerCase();
    return (!query || haystack.includes(query)) && (!category || item.category === category);
  });
  if (!filtered.length) {
    marketplaceListEl.innerHTML = `<div class="template-empty" ${uiAttrs("No marketplace templates found.")}>${escapeHtml(agentT("No marketplace templates found."))}</div>`;
    return;
  }
  marketplaceListEl.innerHTML = filtered.map((item) => {
    const price = Number(item.price || 0);
    const platformFee = Number(item.platformFee ?? price * 0.25).toFixed(2);
    const developerShare = Number(item.developerShare ?? price * 0.75).toFixed(2);
    const status = item.status || item.reviewStatus || "listed";
    const canBuy = status === "listed" || status === "approved" || item.source === "library";
    return `
      <article class="template-card marketplace-card ${escapeHtml(templateCategoryClass(item.category))}">
        <div class="template-card-main">
          <div class="template-card-top">
            <span class="template-category">${escapeHtml(item.category || "Workflow")}</span>
            <span class="template-file">${price ? `$${price.toFixed(2)}` : uiLabel("Free")}</span>
          </div>
          <h2>${item.name ? escapeHtml(item.name) : uiLabel("Marketplace Template")}</h2>
          <p>${item.description ? escapeHtml(item.description) : uiLabel("Reusable workflow template.")}</p>
          <span class="marketplace-status-pill status-${escapeHtml(status)}">${uiLabel(status.replaceAll("_", " "))}</span>
          <div class="marketplace-meta">
            <span>${uiLabel("Developer:")} ${item.developerName ? escapeHtml(item.developerName) : uiLabel("Developer")}</span>
            <span>${uiLabel("Platform fee:")} $${escapeHtml(platformFee)}</span>
            <span>${uiLabel("Developer share:")} $${escapeHtml(developerShare)}</span>
          </div>
        </div>
        <div class="template-card-actions">
          ${status === "pending_review" ? `<button type="button" data-review-marketplace-template="${escapeHtml(item.id)}" ${uiAttrs("Approve")}>${escapeHtml(agentT("Approve"))}</button>` : ""}
          <button type="button" data-buy-marketplace-template="${escapeHtml(item.id)}" ${canBuy ? "" : "disabled"}>${uiLabel(price ? "Checkout" : "Install")}</button>
          <button class="primary" type="button" data-import-marketplace-template="${escapeHtml(item.id)}" ${uiAttrs("Import")}>${escapeHtml(agentT("Import"))}</button>
          <button class="danger" type="button" data-delete-marketplace-template="${escapeHtml(marketplaceItemKey(item))}" ${uiAttrs("Delete")}>${escapeHtml(agentT("Delete"))}</button>
        </div>
      </article>
    `;
  }).join("");
}

async function publishMarketplaceTemplate(event) {
  event.preventDefault();
  const template = buildWorkflowTemplate();
  const payload = {
    name: document.getElementById("marketplaceName")?.value || template.name,
    category: document.getElementById("marketplaceCategory")?.value || "Workflow",
    price: document.getElementById("marketplacePrice")?.value || 0,
    developerName: document.getElementById("marketplaceDeveloper")?.value || "Cell AI Data Developer",
    developerEmail: document.getElementById("marketplaceDeveloperEmail")?.value || marketplaceUser()?.email || "",
    description: document.getElementById("marketplaceDescription")?.value || template.description,
    license: "Single business workspace",
    marketplaceToken: marketplaceToken(),
    template,
  };
  try {
    const response = await fetch(`${apiBase}/marketplace/templates`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await response.json();
    if (!response.ok || !data.ok) throw new Error(data.message || "Could not publish template.");
    marketplaceItems.unshift(data.item);
    alert(agentT("Submitted \"{name}\" for review. Approve it before paid checkout.", { name: data.item.name }));
  } catch (error) {
    const price = Number(payload.price || 0);
    const item = {
      id: `local-${Date.now()}`,
      ...payload,
      price,
      currency: "USD",
      platformFee: Math.round(price * 25) / 100,
      developerShare: Math.round(price * 75) / 100,
      status: "pending_review",
      reviewStatus: "pending_review",
      createdAt: new Date().toISOString(),
    };
    saveLocalMarketplaceItem(item);
    marketplaceItems.unshift(item);
    alert(agentT("Published locally for demo. API note: {message}", { message: error.message }));
  }
  renderMarketplaceCategoryFilter();
  renderMarketplace();
}

async function marketplaceTemplateData(item) {
  if (item.template) return item.template;
  if (item.source === "library" && item.file) {
    return fetchLibraryTemplate({ file: item.file });
  }
  throw new Error("Template JSON is not available for this listing.");
}

async function importMarketplaceTemplate(item) {
  const workflow = addWorkflowFromTemplate(await marketplaceTemplateData(item), true);
  alert(agentT("Imported marketplace template \"{name}\" as a workflow tab.", { name: workflow.name }));
  if (marketplacePanel) marketplacePanel.hidden = true;
}

async function buyMarketplaceTemplate(item) {
  const price = Number(item.price || 0);
  let purchase = null;
  if (!String(item.id || "").startsWith("library-") && !String(item.id || "").startsWith("local-")) {
    try {
      const user = marketplaceUser();
      const response = await fetch(`${apiBase}/marketplace/checkout`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ templateId: item.id, buyerEmail: user?.email || "demo-buyer@company.com" }),
      });
      const data = await response.json();
      if (data.checkoutUrl) {
        window.open(data.checkoutUrl, "_blank", "noopener");
        return;
      }
      if (data.mode === "setup_required") {
        alert(agentT("{message}\nPlatform commission: ${fee}\nDeveloper payout: ${payout}", { message: data.message, fee: Number(data.platformFee || 0).toFixed(2), payout: Number(data.developerPayout || 0).toFixed(2) }));
        return;
      }
      if (response.ok && data.ok) purchase = data.purchase;
    } catch (error) {
      console.warn("Marketplace checkout API unavailable.", error);
    }
  }
  const fee = Number(purchase?.platformFee ?? price * 0.25).toFixed(2);
  const payout = Number(purchase?.developerPayout ?? price * 0.75).toFixed(2);
  alert(agentT("{message}\nPlatform commission: ${fee}\nDeveloper payout: ${payout}", { message: agentT(price ? "Checkout ready" : "Free install ready") + ".", fee, payout }));
}

async function approveMarketplaceTemplate(item) {
  const adminToken = window.prompt(agentT("Enter marketplace admin review token"));
  if (!adminToken) return;
  try {
    const response = await fetch(`${apiBase}/marketplace/templates/review`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ templateId: item.id, status: "listed", adminToken, reviewedBy: marketplaceUser()?.email || "Cell AI Data admin" }),
    });
    const data = await response.json();
    if (!response.ok || !data.ok) throw new Error(data.message || "Could not approve template.");
    const index = marketplaceItems.findIndex((entry) => entry.id === item.id);
    if (index >= 0) marketplaceItems[index] = data.item;
    renderMarketplace();
    alert(agentT("Approved \"{name}\". It is now available for checkout.", { name: data.item.name }));
  } catch (error) {
    alert(agentT(error.message || "Could not approve template."));
  }
}

async function deleteMarketplaceTemplate(item) {
  const name = item.name || "this marketplace template";
  if (!window.confirm(agentT("Delete \"{name}\" from Marketplace?", { name }))) return;

  let serverDeleted = false;
  const isServerItem = item.id && !String(item.id).startsWith("library-") && !String(item.id).startsWith("local-");
  if (isServerItem) {
    try {
      const user = marketplaceUser();
      const response = await fetch(`${apiBase}/marketplace/templates/delete`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          templateId: item.id,
          developerEmail: user?.email || item.developerEmail || "",
          marketplaceToken: marketplaceToken(),
        }),
      });
      const data = await response.json();
      if (!response.ok || !data.ok) throw new Error(data.message || "Could not delete this template on the server.");
      serverDeleted = true;
    } catch (error) {
      console.warn("Marketplace server delete unavailable; hiding item locally.", error);
    }
  }

  hideMarketplaceItem(item);
  alert(agentT(serverDeleted ? "Deleted \"{name}\" from Marketplace." : "Removed \"{name}\" from this Marketplace list.", { name }));
}

const commonIntegrationFields = {
  oauth: [
    ["clientId", "OAuth Client ID", "text", "client_id from provider console"],
    ["clientSecret", "OAuth Client Secret", "password", "store in backend secret manager"],
    ["redirectUri", "Redirect URI", "url", "https://app.cellaidata.com/ext-api/oauth/callback"],
    ["scopes", "Scopes", "text", "read/write permissions requested"],
  ],
  apiKey: [
    ["apiKey", "API Key", "password", "provider API key"],
    ["baseUrl", "Base URL", "url", "optional custom API endpoint"],
  ],
  webhook: [
    ["webhookSecret", "Webhook Signing Secret", "password", "verify inbound webhook signatures"],
  ],
};

function field(key, label, type, placeholder, options = null, visibleWhen = null) {
  return { key, label, type, placeholder, options, visibleWhen };
}

function normalizeField(item) {
  if (!Array.isArray(item)) return item;
  return field(item[0], item[1], item[2], item[3], item[4], item[5]);
}

function fieldIsVisible(item, node) {
  const descriptor = normalizeField(item);
  if (!descriptor.visibleWhen) return true;
  return descriptor.visibleWhen(node.integrationSettings || {}, node);
}

function visibleIntegrationFields(spec, node) {
  return spec.fields.map(normalizeField).filter((item) => fieldIsVisible(item, node));
}

function aiProviderFromNode(node) {
  if (node.name.startsWith("OpenAI")) return "OpenAI";
  if (node.name.startsWith("Claude")) return "Anthropic Claude";
  if (node.name.startsWith("Google Gemini")) return "Google Gemini";
  if (node.name.startsWith("DeepSeek")) return "DeepSeek";
  if (node.name.startsWith("Mistral")) return "Mistral";
  if (node.name.startsWith("Llama")) return "Meta Llama / Compatible";
  if (node.name.startsWith("Perplexity")) return "Perplexity";
  if (node.name.startsWith("Ollama")) return "Ollama Local";
  return "AI Provider";
}

function defaultModelName(node) {
  return {
    "OpenAI GPT-5.6": "gpt-5",
    "OpenAI GPT-5": "gpt-5",
    "OpenAI GPT-5 mini": "gpt-5",
    "Claude Sonnet 5": "claude-sonnet-5",
    "Claude Opus 5": "claude-opus-5",
    "Google Gemini": "gemini-2.5-pro",
    "DeepSeek": "deepseek-reasoner",
    "Mistral": "mistral-large-latest",
    "Llama": "llama-3.1-405b",
    "Perplexity": "sonar-pro",
    "Ollama Local Model": "llama3.1",
  }[node.name] || "";
}

function normalizeAiModelName(model, node) {
  const value = String(model || "").trim();
  if (node.type !== "ai" || aiProviderFromNode(node) !== "OpenAI") return value;
  if (!value || value.includes("/") || value.startsWith("OpenAI") || value === "gpt-5-mini" || value === "gpt-5.6-mini") {
    return "gpt-5";
  }
  return value;
}

function buildAiModelSpec(node) {
  const provider = aiProviderFromNode(node);
  return {
    title: `${provider} Model Step`,
    summary: "Choose how this workflow pays for and runs model calls. BYOK bills the user's provider account; manual web handoff avoids platform API tokens but cannot auto-continue without pasted output.",
    fields: [
      field("authMode", "Connection Mode", "select", "Choose who owns usage and billing", [
        ["platform_api_key", "Use platform API key"],
        ["bring_your_own_api_key", "User API key (BYOK)"],
        ["manual_web_handoff", "Manual ChatGPT / web handoff"],
      ]),
      field("model", "Model", "text", defaultModelName(node) || "model name", null, (settings) => settings.authMode !== "manual_web_handoff"),
      field("platformSecretName", "Backend Secret Name", "text", `${provider.toLowerCase().replaceAll(" ", "_")}_api_key`, null, (settings) => settings.authMode === "platform_api_key"),
      field("apiKey", "User API Key", "password", "stored per customer/user in backend secret storage", null, (settings) => settings.authMode === "bring_your_own_api_key"),
      field("baseUrl", "Compatible Base URL", "url", "optional OpenAI-compatible endpoint", null, (settings) => settings.authMode === "bring_your_own_api_key"),
      field("projectId", "Project / Org / Workspace ID", "text", "optional project, org, or workspace id", null, (settings) => settings.authMode === "bring_your_own_api_key"),
      field("chatUrl", "Manual Web URL", "url", provider === "OpenAI" ? "https://chatgpt.com/" : "provider chat console URL", null, (settings) => settings.authMode === "manual_web_handoff"),
      field("promptTemplate", "Prompt Template", "textarea", "Use {{order}}, {{customer}}, {{previous_step}} placeholders"),
      field("returnFormat", "Expected Return Format", "textarea", "JSON fields the model should return"),
      field("manualResult", "Pasted GPT Result", "textarea", "Paste ChatGPT JSON output here after running the copied prompt", null, (settings) => settings.authMode === "manual_web_handoff"),
      field("dataPolicy", "Data Policy", "text", "mask PII, customer consent, or internal-only context"),
    ],
  };
}

function buildLogicSpec(node) {
  const isSwitch = node.name === "Switch / Match" || /switch/i.test(node.name || "");
  const isFilter = node.name === "Filter Records";
  const isCompare = node.name === "Value Compare";
  return {
    title: `${node.name} Rule`,
    summary: "Configure how this node decides the next workflow path. These fields are saved with the visual workflow draft and can later map to backend execution logic.",
    fields: [
      field("inputSource", "Input Source", "select", "Which data enters this rule", [
        ["previous_step", "Previous step output"],
        ["order", "Order record"],
        ["customer", "Customer record"],
        ["line_items", "Order line items"],
        ["manual", "Manual expression"],
      ]),
      field("fieldPath", "Field Path", "text", "for example payment_status, total, shipping_country"),
      field("operator", "Operator", "select", "Comparison operator", [
        ["equals", "equals"],
        ["not_equals", "not equals"],
        ["contains", "contains"],
        ["greater_than", "greater than"],
        ["less_than", "less than"],
        ["between", "between"],
        ["is_empty", "is empty"],
        ["exists", "exists"],
      ], () => !isSwitch),
      field("compareValue", "Compare Value", "text", "for example Captured, 100, US", null, () => !isSwitch && !isFilter),
      field("filterExpression", "Filter Expression", "textarea", "status == 'paid' && total > 100", null, () => isFilter),
      field("cases", "Cases", "textarea", "US -> FedEx\nCA -> UPS\ndefault -> Manual Review", null, () => isSwitch),
      field("trueLabel", "True Path Label", "text", "Yes / matched"),
      field("falseLabel", "False Path Label", "text", "No / fallback"),
      field("expressionPreview", "Readable Logic", "textarea", isCompare ? "If order.total > 100 route to approval." : "Describe the decision in plain English."),
    ],
  };
}

function buildControlSpec(node) {
  if (node.name === "Loop Items") {
    return {
      title: "Loop Control",
      summary: "Run downstream nodes once for every selected item, with guardrails to avoid runaway automation.",
      fields: [
        field("collectionPath", "Collection Path", "text", "line_items, shipments, imported_rows"),
        field("itemAlias", "Item Alias", "text", "item"),
        field("maxIterations", "Max Iterations", "text", "100"),
        field("onEmpty", "When Empty", "select", "What to do when no items exist", [["skip", "Skip"], ["continue", "Continue"], ["error", "Mark error"]]),
      ],
    };
  }
  if (node.name === "Wait / Delay") {
    return {
      title: "Delay Control",
      summary: "Pause a workflow before continuing to the next node.",
      fields: [
        field("delayMode", "Delay Mode", "select", "Duration or exact time", [["duration", "Duration"], ["until_time", "Until exact time"], ["until_event", "Until event arrives"]]),
        field("duration", "Duration", "text", "15 minutes, 2 hours, 1 day", null, (settings) => settings.delayMode !== "until_time"),
        field("runAt", "Run At", "text", "2026-09-01 09:00:00", null, (settings) => settings.delayMode === "until_time"),
        field("timeoutAction", "Timeout Action", "select", "What happens after waiting", [["continue", "Continue"], ["retry", "Retry previous"], ["stop", "Stop workflow"]]),
      ],
    };
  }
  if (node.name === "Retry / Error Handler") {
    return {
      title: "Retry / Error Handler",
      summary: "Define retry rules and exception routing for failed API calls or workflow steps.",
      fields: [
        field("maxRetries", "Max Retries", "text", "3"),
        field("backoff", "Backoff", "select", "Retry spacing", [["fixed", "Fixed"], ["exponential", "Exponential"], ["manual", "Manual review"]]),
        field("retryDelay", "Retry Delay", "text", "30 seconds"),
        field("failurePath", "Failure Path Label", "text", "Exception / Manual Review"),
        field("logTable", "Log Table", "text", "cx_workflow_log"),
      ],
    };
  }
  if (node.name === "Stop Workflow") {
    return {
      title: "Stop Control",
      summary: "End this workflow path and record a clear reason.",
      fields: [
        field("finalStatus", "Final Status", "select", "Workflow result", [["completed", "Completed"], ["cancelled", "Cancelled"], ["failed", "Failed"], ["ignored", "Ignored"]]),
        field("reason", "Reason", "textarea", "Why this path should stop."),
      ],
    };
  }
  return {
    title: "Human Approval",
    summary: "Pause the flow until an operator reviews the payload and chooses the next action.",
    fields: [
      field("approverRole", "Approver Role", "text", "Operations Manager"),
      field("approvalMessage", "Approval Message", "textarea", "Please review this order exception."),
      field("approveLabel", "Approve Button Label", "text", "Approve"),
      field("rejectLabel", "Reject Button Label", "text", "Reject"),
      field("timeout", "Timeout", "text", "24 hours"),
    ],
  };
}

function buildEmailSpec(node) {
  const provider = node.name.includes("Gmail") ? "Gmail" : node.name.includes("Outlook") ? "Outlook" : "Email";
  return {
    title: `${provider} Customer Email`,
    summary: "Prepare or send a customer email from previous workflow output. SMTP credentials are read from backend secrets, not stored in the workflow template.",
    fields: [
      field("deliveryMode", "Delivery Mode", "select", "preview or connected provider", [
        ["preview", "Preview only"],
        ["connected_provider", "Send with connected provider"],
      ]),
      field("to", "Customer Email", "text", "customer@example.com"),
      field("smsGatewayEmail", "SMS Gateway Email", "text", "9496597928@tmomail.net, 6263833666@tmomail.net"),
      field("phoneNumber", "Phone Number Memo", "text", "9496597928, 6263833666"),
      field("subjectTemplate", "Subject Template", "text", "{{email.subject}}"),
      field("bodyTemplate", "Body Template", "textarea", "{{email.body}}"),
      field("smtpHost", "SMTP Host", "text", "smtp.gmail.com", null, (settings) => settings.deliveryMode === "connected_provider"),
      field("smtpPort", "SMTP Port", "text", "587", null, (settings) => settings.deliveryMode === "connected_provider"),
      field("smtpSecurity", "Security", "select", "STARTTLS", [["starttls", "STARTTLS"], ["ssl", "SSL"], ["none", "None"]], (settings) => settings.deliveryMode === "connected_provider"),
      field("username", "Gmail Username", "text", "your Gmail address", null, (settings) => settings.deliveryMode === "connected_provider"),
      field("fromEmail", "From Email", "text", "same as Gmail username", null, (settings) => settings.deliveryMode === "connected_provider"),
      field("passwordSecretName", "Backend Password Secret", "text", "GMAIL_APP_PASSWORD", null, (settings) => settings.deliveryMode === "connected_provider"),
    ],
  };
}

function buildTwilioSmsSpec() {
  return {
    title: "Twilio SMS",
    summary: "Send real SMS messages through Twilio. Store production credentials as backend environment secrets instead of saving raw tokens in workflow JSON.",
    fields: [
      field("deliveryMode", "Delivery Mode", "select", "preview or connected provider", [
        ["preview", "Preview only"],
        ["connected_provider", "Send with Twilio"],
      ]),
      field("toNumbers", "To Phone Numbers", "text", "9493128694, 6263833666"),
      field("messageTemplate", "Message Template", "textarea", "{{sms}}"),
      field("accountSidSecretName", "Account SID Secret", "text", "TWILIO_ACCOUNT_SID", null, (settings) => settings.deliveryMode === "connected_provider"),
      field("authTokenSecretName", "Auth Token Secret", "text", "TWILIO_AUTH_TOKEN", null, (settings) => settings.deliveryMode === "connected_provider"),
      field("fromNumberSecretName", "From Number Secret", "text", "TWILIO_FROM_NUMBER", null, (settings) => settings.deliveryMode === "connected_provider"),
      field("fromNumber", "From Number Override", "text", "+1 Twilio phone number, optional", null, (settings) => settings.deliveryMode === "connected_provider"),
    ],
  };
}

function tableFromCellXNode(node) {
  const match = String(node.action || "").match(/\/table\/([^/]+)$/);
  if (match) return match[1];
  const labelMatch = String(node.name || "").match(/:\s*([a-zA-Z0-9_]+)$/);
  return labelMatch ? labelMatch[1] : "";
}

function operationFromCellXNode(node) {
  if (/detail/i.test(node.name)) return "detail";
  if (/insert/i.test(node.name)) return "insert";
  if (/update/i.test(node.name)) return "update";
  if (/delete/i.test(node.name)) return "delete";
  if (/upsert/i.test(node.name)) return "upsert";
  if (/bulk import/i.test(node.name)) return "bulk_import";
  if (/export excel/i.test(node.name)) return "export_excel";
  return "query";
}

function cellxTableOptions() {
  const tables = Array.isArray(cellxSchema?.tables) ? cellxSchema.tables : [];
  const priority = (name) => {
    if (/^(cx_|cellx_|gen_)/i.test(name)) return 0;
    if (/^sys_/i.test(name)) return 1;
    if (/^QRTZ_/i.test(name)) return 3;
    return 2;
  };
  const options = [...tables]
    .sort((a, b) => priority(a.name) - priority(b.name) || a.name.localeCompare(b.name))
    .map((table) => [table.name, `${table.name} (${table.columnCount || 0} fields)`]);
  return options.length ? options : [["", "Load CellX tables..."]];
}

function selectedCellXTable(node) {
  const name = node.integrationSettings?.tableName || tableFromCellXNode(node);
  const tables = Array.isArray(cellxSchema?.tables) ? cellxSchema.tables : [];
  return tables.find((table) => table.name === name) || null;
}

function cellxColumnOptions(node) {
  const table = selectedCellXTable(node);
  const columns = Array.isArray(table?.columns) ? table.columns : [];
  return columns.map((column) => [column.name, `${column.name} (${column.type})`]);
}

function buildCellXDatabaseSpec(node) {
  const defaultTable = tableFromCellXNode(node);
  const defaultOperation = operationFromCellXNode(node);
  return {
    title: "CellX Database Operation",
    summary: "Access CellX backend data through controlled CRUD steps. Use allowlisted tables, parameterized filters, and soft-delete defaults before wiring this to real execution.",
    fields: [
      field("operation", "Operation", "select", "CRUD action", [
        ["query", "Query rows"],
        ["detail", "Get detail"],
        ["insert", "Insert row"],
        ["update", "Update row"],
        ["delete", "Delete row"],
        ["upsert", "Upsert row"],
        ["bulk_import", "Bulk import"],
        ["export_excel", "Export Excel"],
      ]),
      field("tableName", "Table", "select", defaultTable || "Choose a CellX table", cellxTableOptions()),
      field("primaryKey", "Primary Key", "text", "id or uuid", null, (settings) => ["detail", "update", "delete", "upsert"].includes(settings.operation || defaultOperation)),
      field("whereClause", "WHERE / Filter", "textarea", "del_flag = '0' AND status = {{status}}", null, (settings) => ["query", "detail", "update", "delete", "export_excel"].includes(settings.operation || defaultOperation)),
      field("sortBy", "Sort By", "text", "create_time desc", null, (settings) => ["query", "export_excel"].includes(settings.operation || defaultOperation)),
      field("limit", "Row Limit", "text", "200", null, (settings) => ["query", "export_excel"].includes(settings.operation || defaultOperation)),
      field("fieldMapping", "Field Mapping / Values", "textarea", "asin <- {{item.asin}}\ntitle <- {{item.title}}\nprice <- {{item.price}}", null, (settings) => ["insert", "update", "upsert", "bulk_import"].includes(settings.operation || defaultOperation)),
      field("inputPayload", "Input Payload Path", "text", "{{previous_step.rows}}", null, (settings) => ["insert", "upsert", "bulk_import"].includes(settings.operation || defaultOperation)),
      field("softDelete", "Delete Mode", "select", "Prefer soft delete", [["soft", "Soft delete: set del_flag = 1"], ["hard", "Hard delete: DELETE row"]], (settings) => (settings.operation || defaultOperation) === "delete"),
      field("excelFileName", "Excel File Name", "text", "cellx_export.xlsx", null, (settings) => (settings.operation || defaultOperation) === "export_excel"),
      field("safetyMode", "Safety Mode", "select", "Execution guardrail", [
        ["read_only", "Read only"],
        ["draft_write", "Draft write / preview SQL"],
        ["approved_write", "Approved write"],
      ]),
      field("auditLog", "Audit Log Table", "text", "cx_workflow_log"),
    ],
  };
}

const integrationSpecs = {
  "FedEx": {
    title: "FedEx Shipping API",
    summary: "Needed for rates, labels, tracking, pickup and delivery event workflows.",
    fields: [
      ["accountNumber", "FedEx Account Number", "text", "shipping account number"],
      ["apiKey", "API Key / Client ID", "password", "FedEx developer project key"],
      ["apiSecret", "API Secret", "password", "FedEx developer project secret"],
      ["environment", "Environment", "text", "sandbox or production"],
      ...commonIntegrationFields.webhook,
    ],
  },
  "UPS": {
    title: "UPS Shipping API",
    summary: "Needed for OAuth access, rating, labels, tracking and shipper account billing.",
    fields: [
      ["clientId", "UPS Client ID", "text", "UPS app client id"],
      ["clientSecret", "UPS Client Secret", "password", "UPS app client secret"],
      ["shipperNumber", "Shipper Number", "text", "UPS shipper number"],
      ["accountNumber", "Billing Account", "text", "optional billing account"],
      ["environment", "Environment", "text", "sandbox or production"],
    ],
  },
  "USPS": {
    title: "USPS API",
    summary: "Needed for domestic labels, address validation and tracking.",
    fields: [
      ["clientId", "USPS Client ID", "text", "USPS developer app client id"],
      ["clientSecret", "USPS Client Secret", "password", "USPS developer app secret"],
      ["mailerId", "Mailer ID", "text", "optional USPS mailer id"],
    ],
  },
  "DHL": {
    title: "DHL API",
    summary: "Needed for international labels, rates, tracking and customs paperwork.",
    fields: [
      ["accountNumber", "DHL Account Number", "text", "DHL billing account"],
      ["apiKey", "API Key", "password", "DHL developer key"],
      ["apiSecret", "API Secret", "password", "DHL developer secret"],
    ],
  },
  "Stripe": {
    title: "Stripe Payments",
    summary: "Needed for checkout sessions, payment intents, refunds and webhook events.",
    fields: [
      ["publishableKey", "Publishable Key", "text", "pk_live_..."],
      ["secretKey", "Secret Key", "password", "sk_live_..."],
      ["webhookSecret", "Webhook Signing Secret", "password", "whsec_..."],
      ["accountId", "Connected Account ID", "text", "optional acct_..."],
    ],
  },
  "PayPal": {
    title: "PayPal Checkout",
    summary: "Needed for order creation, capture, refunds and dispute workflows.",
    fields: [
      ["clientId", "PayPal Client ID", "text", "live app client id"],
      ["clientSecret", "PayPal Client Secret", "password", "live app secret"],
      ["merchantId", "Merchant ID", "text", "PayPal merchant id"],
      ["environment", "Environment", "text", "sandbox or live"],
    ],
  },
  "Amazon SP-API": {
    title: "Amazon Selling Partner API",
    summary: "Needed for seller authorization, marketplace orders, inventory and fulfillment updates.",
    fields: [
      ["sellerId", "Seller ID", "text", "Amazon seller id"],
      ["marketplaceId", "Marketplace ID", "text", "for example ATVPDKIKX0DER"],
      ["lwaClientId", "LWA Client ID", "text", "Login with Amazon client id"],
      ["lwaClientSecret", "LWA Client Secret", "password", "Login with Amazon secret"],
      ["refreshToken", "Refresh Token", "password", "seller authorization refresh token"],
      ["awsRoleArn", "AWS Role ARN", "text", "IAM role used by SP-API app"],
      ["awsRegion", "AWS Region", "text", "for example us-east-1"],
    ],
  },
  "Shopify": {
    title: "Shopify Admin API",
    summary: "Needed for store orders, products, customers, fulfillment and webhook sync.",
    fields: [
      ["storeDomain", "Store Domain", "text", "your-store.myshopify.com"],
      ["adminAccessToken", "Admin Access Token", "password", "shpat_..."],
      ["apiSecret", "API Secret / Webhook Secret", "password", "used to verify webhooks"],
    ],
  },
  "MySQL": {
    title: "MySQL Connection",
    summary: "Needed for approved database reads/writes from workflow steps.",
    fields: [
      ["host", "Host", "text", "127.0.0.1 or database host"],
      ["port", "Port", "text", "3306"],
      ["database", "Database", "text", "cellx_base"],
      ["username", "Username", "text", "least-privilege database user"],
      ["password", "Password", "password", "database password"],
    ],
  },
};

function buildIntegrationSpec(node) {
  if (node.type === "trigger" && node.action === "cron") {
    return {
      title: "Daily Schedule",
      summary: "Server schedule and timezone",
      fields: [
        field("scheduleEnabled", "Daily Schedule", "select", "", [["false", "Disabled"], ["true", "Enabled"]]),
        field("schedule", "Daily Run Time", "daily-time", ""),
        field("timezone", "Timezone", "text", "America/Los_Angeles"),
        field("owner", "Owner", "text", "optional team or operator"),
      ],
    };
  }
  if (!node) return null;
  if (integrationSpecs[node.name]) return integrationSpecs[node.name];
  if (node.name === "JSON Transform" || String(node.action || "").includes("/json-transform")) {
    return {
      title: "JSON Transform Settings",
      summary: "Read the previous node output and map it into clean fields for CellX DB, Excel export, or the next workflow step.",
      fields: [
        field("sourcePath", "Source Path", "text", "previous_step or previous_step.result"),
        field("transformMapping", "Field Mapping", "textarea", "target_field <- {{result.source_field}}"),
        field("outputMode", "Output Mode", "select", "object or rows", [
          ["object", "Single JSON object"],
          ["rows", "One-row table for Excel / CellX"],
        ]),
      ],
    };
  }
  if (node.name === "Gmail" || node.name === "Outlook Email" || String(node.action || "").includes("/mail") || String(node.action || "").includes("/gmail/send")) {
    return buildEmailSpec(node);
  }
  if (node.name === "Twilio SMS" || String(node.action || "").includes("/twilio/sms")) {
    return buildTwilioSmsSpec(node);
  }
  if (node.name === "Google Sheets" || String(node.action || "").includes("/google/sheets")) {
    return {
      title: "Google Sheets Append",
      summary: "Append normalized workflow rows into a Google Sheet. Use a service account or OAuth connection with write access to the target spreadsheet.",
      fields: [
        field("authMode", "Auth Mode", "select", "How Google access is provided", [
          ["service_account_or_oauth", "Service account or OAuth"],
          ["service_account", "Service account JSON"],
          ["oauth", "Google OAuth"],
        ]),
        field("spreadsheetId", "Spreadsheet ID", "text", "Google Sheet ID from the URL"),
        field("sheetName", "Sheet Tab Name", "text", "Form Submissions"),
        field("appendMode", "Write Mode", "select", "Append or replace rows", [
          ["append_rows", "Append rows"],
          ["replace_sheet", "Replace sheet"],
        ]),
        field("inputPayload", "Input Payload Path", "text", "{{previous_step.rows}}"),
        field("fieldMapping", "Column Mapping", "textarea", "Sheet Column <- workflow_field"),
        field("serviceAccountJson", "Service Account JSON", "password", "optional backend/service account credential"),
        field("timeout", "Timeout Seconds", "text", "30"),
      ],
    };
  }
  if (node.name.startsWith("Google ")) {
    return {
      title: "Google Workspace OAuth",
      summary: "Needed to access Google Docs, Sheets, Drive, Forms, Slides or Calendar on behalf of a workspace account.",
      fields: [...commonIntegrationFields.oauth, ["serviceAccountJson", "Service Account JSON", "password", "optional server-to-server credential"]],
    };
  }
  if (node.name.startsWith("Outlook") || node.name.startsWith("Microsoft") || node.name === "OneDrive" || node.name === "SharePoint") {
    return {
      title: "Microsoft Graph OAuth",
      summary: "Needed to access Outlook, Calendar, Teams, Word, Excel, OneDrive and SharePoint through Microsoft Graph.",
      fields: [["tenantId", "Azure Tenant ID", "text", "common, organizations, or tenant id"], ...commonIntegrationFields.oauth],
    };
  }
  if (["Slack", "Discord", "Telegram Bot", "WhatsApp Business", "Mailchimp", "LinkedIn"].includes(node.name)) {
    return {
      title: "Communication Connector",
      summary: "Needed for sending messages, receiving callbacks and verifying event webhooks.",
      fields: [["accountId", "Account / Workspace ID", "text", "workspace, phone, or business id"], ["apiToken", "API Token", "password", "bot token or access token"], ...commonIntegrationFields.webhook],
    };
  }
  if (["HubSpot", "Salesforce", "Pipedrive", "Zoho CRM", "Zendesk", "Intercom", "Freshdesk"].includes(node.name)) {
    return {
      title: "CRM / Support OAuth",
      summary: "Needed to sync contacts, deals, tickets, conversations and support events.",
      fields: [...commonIntegrationFields.oauth, ["accountDomain", "Account Domain", "text", "company instance or subdomain"]],
    };
  }
  if (["OpenAI GPT-5.6", "OpenAI GPT-5", "OpenAI GPT-5 mini", "Claude Sonnet 5", "Claude Opus 5", "Google Gemini", "DeepSeek", "Mistral", "Llama", "Perplexity", "Ollama Local Model"].includes(node.name) || node.type === "ai") {
    return buildAiModelSpec(node);
  }
  if (node.type === "condition") {
    return buildLogicSpec(node);
  }
  if (node.type === "control") {
    return buildControlSpec(node);
  }
  if (node.type === "database") {
    return integrationSpecs.MySQL;
  }
  if (node.type === "cellx-db") {
    return buildCellXDatabaseSpec(node);
  }
  if (node.type === "tool") {
    return {
      title: "Agent Tool Settings",
      summary: "Needed to run utility steps safely inside a workflow.",
      fields: [["endpoint", "Endpoint", "url", "target API or internal endpoint"], ["authHeader", "Auth Header", "password", "Bearer token or signed header"], ["timeout", "Timeout Seconds", "text", "30"], ["retryPolicy", "Retry Policy", "text", "3 retries, exponential backoff"]],
    };
  }
  if (node.type === "external-agent" || String(node.action || "").includes("/external-agent/run")) {
    return {
      title: "External Agent Connector",
      summary: "Connect a customer-owned agent to this workflow. Default dry-run previews the payload; enable Execute Live only after the endpoint and auth are verified.",
      fields: [
        field("agentName", "Agent Name", "text", "Customer Lead Scoring Agent"),
        field("runLocation", "Run Location", "select", "Where this agent executes", [
          ["cellai_cloud", "Cell AI Data Cloud"],
          ["customer_local", "Customer Local Runner"],
          ["customer_private", "Customer Private Server"],
        ]),
        field("runnerName", "Runner Name", "text", "office-laptop-runner", null, (settings) => settings.runLocation === "customer_local" || settings.runLocation === "customer_private"),
        field("connectionType", "Connection Type", "select", "API, webhook, script, or MCP-style", [
          ["api", "HTTP API"],
          ["webhook", "Webhook"],
          ["script", "Approved backend script"],
          ["github_repo", "GitHub repo agent"],
          ["mcp", "MCP-style contract"],
        ]),
        field("repoUrl", "Agent Repo", "url", "https://github.com/TauricResearch/TradingAgents", null, (settings) => settings.connectionType === "github_repo" || settings.runLocation === "customer_local"),
        field("branch", "Branch / Ref", "text", "main", null, (settings) => settings.connectionType === "github_repo" || settings.runLocation === "customer_local"),
        field("installCommand", "Install Command", "text", "pip install -r requirements.txt", null, (settings) => settings.connectionType === "github_repo" || settings.runLocation === "customer_local"),
        field("runCommand", "Run Command", "text", "python cellx_agent_adapter.py", null, (settings) => settings.connectionType === "github_repo" || settings.runLocation === "customer_local"),
        field("secretEnvNames", "Secrets from Local Runner", "text", "OPENAI_API_KEY,FINNHUB_API_KEY", null, (settings) => settings.connectionType === "github_repo" || settings.runLocation === "customer_local"),
        field("refreshRepo", "Refresh Repo Cache", "select", "Use cached clone", [["false", "Use cached clone"], ["true", "Re-clone this run"]], (settings) => settings.connectionType === "github_repo" || settings.runLocation === "customer_local"),
        field("endpointUrl", "Endpoint URL", "url", "https://agent.example.com/run", null, (settings) => settings.connectionType !== "script" && settings.connectionType !== "github_repo" && settings.runLocation !== "customer_local"),
        field("method", "HTTP Method", "select", "POST", [["POST", "POST"], ["GET", "GET"]], (settings) => settings.connectionType === "api" || settings.connectionType === "webhook" || settings.connectionType === "mcp"),
        field("authType", "Auth Type", "select", "How to authenticate", [
          ["none", "None"],
          ["bearer", "Bearer token"],
          ["api_key_header", "API key header"],
          ["basic", "Basic auth"],
        ], (settings) => settings.connectionType !== "script" && settings.connectionType !== "github_repo" && settings.runLocation !== "customer_local"),
        field("secretName", "Backend Secret Name", "text", "EXTERNAL_AGENT_TOKEN", null, (settings) => settings.connectionType !== "script" && settings.connectionType !== "github_repo" && settings.runLocation !== "customer_local" && settings.authType !== "none"),
        field("apiKeyHeader", "API Key Header", "text", "X-API-Key", null, (settings) => settings.connectionType !== "script" && settings.connectionType !== "github_repo" && settings.runLocation !== "customer_local" && settings.authType === "api_key_header"),
        field("scriptName", "Script Name", "text", "approved_agent.py", null, (settings) => settings.connectionType === "script"),
        field("inputMapping", "Input Mapping JSON", "textarea", "{\"payload\":\"{{previous_step}}\",\"workflow\":\"{{workflow.name}}\"}"),
        field("outputSchema", "Expected Output Schema", "textarea", "{\"ok\":true,\"result\":{},\"rows\":[]}"),
        field("executeLive", "Execute Live", "select", "Dry run is safer for setup", [["false", "Dry run / preview"], ["true", "Call external agent now"]]),
        field("timeout", "Timeout Seconds", "text", "20"),
        field("retryPolicy", "Retry Policy", "text", "2 retries, exponential backoff"),
      ],
    };
  }
  if (node.type === "script") {
    if (node.action === "/ext-api/instagram/run") {
      return {
        title: "Instagram Local Browser",
        summary: "Runs in the Windows portable edition. Test Selected checks configuration; Run Agent likes posts and publishes the comment. First use requires signing in to the separate browser window.",
        fields: [
          ["minPosts", "Minimum posts", "number", "5"],
          ["maxPosts", "Maximum posts", "number", "8"],
          ["commentText", "Public comment", "textarea", "hello, I like your image"],
        ],
      };
    }
    const isOrderDeskScript = String(node.integrationSettings?.scriptName || "").includes("orderdesk_orders_to_carriers.py") || /order desk/i.test(node.name || "");
    if (isOrderDeskScript) {
      return {
        title: "Order Desk Order API",
        summary: "Fetch ecommerce orders from Order Desk and prepare carrier routing payloads. Credentials are used for this workflow step and should be kept private.",
        fields: [
          ["scriptName", "Script Name", "text", "orderdesk_orders_to_carriers.py"],
          ["orderdeskStoreId", "ORDERDESK_STORE_ID", "text", "Store ID from Order Desk API settings"],
          ["orderdeskApiKey", "ORDERDESK_API_KEY", "password", "API Key from Order Desk API settings"],
          ["inputJson", "Input JSON", "textarea", "{\"limit\":10,\"order_by\":\"date_added\",\"order\":\"desc\",\"dry_run\":true}"],
          ["timeout", "Timeout Seconds", "text", "25"],
          ["args", "Arguments", "text", "optional space-separated args"],
        ],
      };
    }
    return {
      title: "Custom Script Runner",
      summary: "Run an approved customer script from the backend script folder. The script receives the Input JSON through stdin and should print JSON to stdout.",
      fields: [
        ["scriptName", "Script Name", "text", "amazon_bestsellers_demo.py"],
        ["inputJson", "Input JSON", "textarea", "{\"source_url\":\"https://www.amazon.com/Best-Sellers/zgbs\",\"limit\":20}"],
        ["timeout", "Timeout Seconds", "text", "20"],
        ["args", "Arguments", "text", "optional space-separated args"],
      ],
    };
  }
  return {
    title: "Basic Step Settings",
    summary: "No provider-specific secret is required unless this step calls an external service.",
    fields: [["owner", "Owner", "text", "team or operator responsible"], ["timeout", "Timeout Seconds", "text", "30"]],
  };
}

function ensureIntegrationSettings(node) {
  node.integrationSettings = node.integrationSettings || {};
  const spec = buildIntegrationSpec(node);
  if (node.type === "trigger" && node.action === "cron") {
    if (!node.integrationSettings.scheduleEnabled) node.integrationSettings.scheduleEnabled = node.name === "Daily Schedule" ? "true" : "false";
    if (!node.integrationSettings.schedule) node.integrationSettings.schedule = "0 6 * * *";
    if (!node.integrationSettings.timezone) node.integrationSettings.timezone = "America/Los_Angeles";
  }
  for (const item of spec.fields.map(normalizeField)) {
    const key = item.key;
    if (!(key in node.integrationSettings)) node.integrationSettings[key] = "";
  }
  if (node.type === "ai" && !node.integrationSettings.authMode) {
    node.integrationSettings.authMode = "bring_your_own_api_key";
  }
  if (node.type === "ai" && !node.integrationSettings.model) {
    node.integrationSettings.model = defaultModelName(node);
  }
  if (node.type === "ai") {
    node.integrationSettings.model = normalizeAiModelName(node.integrationSettings.model, node);
  }
  if (node.type === "ai" && !node.integrationSettings.platformSecretName && node.integrationSettings.authMode === "platform_api_key") {
    const provider = aiProviderFromNode(node);
    node.integrationSettings.platformSecretName = provider === "OpenAI" ? "OPENAI_API_KEY" : `${provider.toLowerCase().replaceAll(" ", "_")}_api_key`;
  }
  if (node.type === "ai" && !node.integrationSettings.promptTemplate) {
    node.integrationSettings.promptTemplate = "Analyze the previous workflow JSON data.\n\nTasks:\n1. Summarize the key information.\n2. Identify important patterns, risks, or opportunities.\n3. Recommend the next workflow action.\n\nPrevious workflow output:\n{{previous_step}}\n\nReturn only valid JSON that matches the expected return format.";
  }
  if (node.type === "ai" && !node.integrationSettings.returnFormat) {
    node.integrationSettings.returnFormat = "{\n  \"summary\": \"short business summary\",\n  \"insights\": [\"insight 1\", \"insight 2\"],\n  \"recommended_action\": \"next action\",\n  \"confidence\": \"high | medium | low\"\n}";
  }
  if (node.type === "ai" && node.integrationSettings.authMode === "manual_web_handoff") {
    if (!node.integrationSettings.chatUrl) node.integrationSettings.chatUrl = "https://chatgpt.com/";
  }
  if (node.name === "JSON Transform" || String(node.action || "").includes("/json-transform")) {
    if (!node.integrationSettings.sourcePath) node.integrationSettings.sourcePath = "previous_step";
    if (!node.integrationSettings.transformMapping) {
      node.integrationSettings.transformMapping = [
        "decision_summary <- {{result.summary}}",
        "recommended_action <- {{result.recommended_action}}",
        "confidence <- {{result.confidence}}",
        "insights <- {{result.insights}}",
        "insight_count <- {{result.insights.length}}",
      ].join("\n");
    }
    if (!node.integrationSettings.outputMode) node.integrationSettings.outputMode = "object";
  }
  if (node.name === "Gmail" || node.name === "Outlook Email" || String(node.action || "").includes("/mail") || String(node.action || "").includes("/gmail/send")) {
    node.integrationSettings.to = appendEmailRecipient(node.integrationSettings.to);
    if (!node.integrationSettings.deliveryMode) node.integrationSettings.deliveryMode = "preview";
    if (!node.integrationSettings.subjectTemplate) node.integrationSettings.subjectTemplate = "{{email.subject}}";
    if (!node.integrationSettings.bodyTemplate) node.integrationSettings.bodyTemplate = "{{email.body}}";
    if (!node.integrationSettings.smtpHost) node.integrationSettings.smtpHost = "smtp.gmail.com";
    if (!node.integrationSettings.smtpPort) node.integrationSettings.smtpPort = "587";
    if (!node.integrationSettings.smtpSecurity) node.integrationSettings.smtpSecurity = "starttls";
    if (!node.integrationSettings.username) node.integrationSettings.username = "sender@example.com";
    if (!node.integrationSettings.fromEmail) node.integrationSettings.fromEmail = "sender@example.com";
    if (!node.integrationSettings.passwordSecretName) node.integrationSettings.passwordSecretName = "GMAIL_APP_PASSWORD";
  }
  if (node.type === "cellx-db") {
    if (!node.integrationSettings.operation) node.integrationSettings.operation = operationFromCellXNode(node);
    if (!node.integrationSettings.tableName) node.integrationSettings.tableName = tableFromCellXNode(node);
    if (!node.integrationSettings.softDelete) node.integrationSettings.softDelete = "soft";
    if (!node.integrationSettings.safetyMode) node.integrationSettings.safetyMode = "read_only";
    if (!node.integrationSettings.auditLog) node.integrationSettings.auditLog = "cx_workflow_log";
  }
  if (node.name === "Google Sheets" || String(node.action || "").includes("/google/sheets")) {
    if (!node.integrationSettings.authMode) node.integrationSettings.authMode = "service_account_or_oauth";
    if (!node.integrationSettings.spreadsheetId) node.integrationSettings.spreadsheetId = "";
    if (!node.integrationSettings.sheetName) node.integrationSettings.sheetName = "Form Submissions";
    if (!node.integrationSettings.appendMode) node.integrationSettings.appendMode = "append_rows";
    if (!node.integrationSettings.inputPayload) node.integrationSettings.inputPayload = "{{previous_step.rows}}";
    if (!node.integrationSettings.fieldMapping) {
      node.integrationSettings.fieldMapping = [
        "Submitted At <- submitted_at",
        "Name <- name",
        "Email <- email",
        "Phone <- phone",
        "Company <- company",
        "Message <- message",
        "Source Page <- source_page",
        "Status <- status",
      ].join("\n");
    }
    if (!node.integrationSettings.timeout) node.integrationSettings.timeout = "30";
  }
  if (node.type === "external-agent") {
    if (!node.integrationSettings.agentName) node.integrationSettings.agentName = node.name || "External Agent";
    if (!node.integrationSettings.runLocation) node.integrationSettings.runLocation = /github/i.test(node.name || "") ? "customer_local" : "customer_private";
    if (!node.integrationSettings.runnerName) node.integrationSettings.runnerName = "customer-runner-1";
    if (!node.integrationSettings.connectionType) node.integrationSettings.connectionType = /github/i.test(node.name || "") ? "github_repo" : "api";
    if (node.integrationSettings.runLocation === "customer_local" && node.integrationSettings.connectionType === "api") {
      node.integrationSettings.connectionType = "github_repo";
    }
    if (!node.integrationSettings.endpointUrl && node.integrationSettings.connectionType !== "github_repo" && node.integrationSettings.runLocation !== "customer_local") node.integrationSettings.endpointUrl = "https://agent.example.com/run";
    if (!node.integrationSettings.method) node.integrationSettings.method = "POST";
    if (!node.integrationSettings.authType) node.integrationSettings.authType = "bearer";
    if (!node.integrationSettings.secretName) node.integrationSettings.secretName = "EXTERNAL_AGENT_TOKEN";
    if (!node.integrationSettings.apiKeyHeader) node.integrationSettings.apiKeyHeader = "X-API-Key";
    if (node.integrationSettings.connectionType === "github_repo" || node.integrationSettings.runLocation === "customer_local") {
      if (!node.integrationSettings.repoUrl) node.integrationSettings.repoUrl = "https://github.com/TauricResearch/TradingAgents";
      if (!node.integrationSettings.branch) node.integrationSettings.branch = "main";
      if (!node.integrationSettings.installCommand) node.integrationSettings.installCommand = "pip install -r requirements.txt";
      if (!node.integrationSettings.runCommand) node.integrationSettings.runCommand = "python cellx_agent_adapter.py";
      if (!node.integrationSettings.secretEnvNames) node.integrationSettings.secretEnvNames = "OPENAI_API_KEY,FINNHUB_API_KEY";
      if (!node.integrationSettings.refreshRepo) node.integrationSettings.refreshRepo = "false";
    }
    if (!node.integrationSettings.inputMapping) node.integrationSettings.inputMapping = '{"payload":"{{previous_step}}","workflow":"{{workflow.name}}"}';
    if (!node.integrationSettings.outputSchema) node.integrationSettings.outputSchema = '{\n  "ok": true,\n  "result": {},\n  "rows": []\n}';
    if (!node.integrationSettings.executeLive) node.integrationSettings.executeLive = "false";
    if (!node.integrationSettings.timeout) node.integrationSettings.timeout = "20";
    if (!node.integrationSettings.retryPolicy) node.integrationSettings.retryPolicy = "2 retries, exponential backoff";
  }
  if (node.type === "script") {
    if (!node.integrationSettings.scriptName) node.integrationSettings.scriptName = "amazon_bestsellers_demo.py";
    if (!node.integrationSettings.inputJson) node.integrationSettings.inputJson = '{"source_url":"https://www.amazon.com/Best-Sellers/zgbs","limit":20}';
    if (!node.integrationSettings.timeout) node.integrationSettings.timeout = "20";
    if (String(node.integrationSettings.scriptName || "").includes("orderdesk_orders_to_carriers.py") || (/order desk/i.test(node.name || "") && node.integrationSettings.scriptName === "amazon_bestsellers_demo.py")) {
      node.integrationSettings.scriptName = "orderdesk_orders_to_carriers.py";
      if (!node.integrationSettings.inputJson || node.integrationSettings.inputJson.includes("amazon_bestsellers_demo.py")) {
        node.integrationSettings.inputJson = '{"limit":100,"order_by":"date_added","order":"desc","dry_run":true}';
      } else {
        try {
          const orderdeskInput = JSON.parse(node.integrationSettings.inputJson);
          if (!orderdeskInput.limit || Number(orderdeskInput.limit) === 10) {
            orderdeskInput.limit = 100;
            node.integrationSettings.inputJson = JSON.stringify(orderdeskInput);
          }
        } catch {
          // Keep custom non-JSON input visible so the user can repair it.
        }
      }
      if (!node.integrationSettings.timeout || node.integrationSettings.timeout === "20") node.integrationSettings.timeout = "25";
    }
  }
  return spec;
}

function isOptionalIntegrationField(key, placeholder = "") {
  return /optional/i.test(placeholder) || ["baseUrl", "projectId", "accountId", "apiToken", "webhookSecret", "serviceAccountJson", "authHeader", "retryPolicy", "dataPolicy", "chatUrl", "manualResult", "args", "trueLabel", "falseLabel", "expressionPreview", "installCommand", "secretEnvNames", "outputSchema"].includes(key);
}

function requiredIntegrationFields(spec, node) {
  return visibleIntegrationFields(spec, node)
    .filter(({ key }) => {
      if (key === "to" && (node.name === "Gmail" || node.name === "Outlook Email" || String(node.action || "").includes("/gmail/send") || String(node.action || "").includes("/mail"))) {
        return false;
      }
      if (key !== "softDelete") return true;
      const operation = node.integrationSettings?.operation || operationFromCellXNode(node);
      return operation === "delete";
    })
    .filter(({ key, placeholder }) => !isOptionalIntegrationField(key, placeholder))
    .map(({ key }) => key);
}

function integrationStatusMarkup(status) {
  if (!status) return "";
  const label = status.status === "success" ? "Connected" : status.status === "manual" ? "Manual handoff ready" : status.status === "testing" ? "Testing" : "Connection failed";
  return `<div class="connection-status ${status.status}"><strong>${uiLabel(label)}</strong>${uiLabel(status.message || "")}</div>`;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function testBadgeLabel(status) {
  if (status === "success") return uiLabel("Pass");
  if (status === "manual") return uiLabel("Manual");
  if (status === "testing") return uiLabel("Testing");
  if (status === "pending") return uiLabel("Pending");
  return uiLabel("Error");
}

function compactJson(value) {
  return JSON.stringify(value, null, 2);
}

async function copyTextToClipboard(text) {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text);
    return;
  }
  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.setAttribute("readonly", "");
  textarea.style.position = "fixed";
  textarea.style.left = "-9999px";
  document.body.appendChild(textarea);
  textarea.select();
  document.execCommand("copy");
  textarea.remove();
}

function selectTextElement(element) {
  if (!element) return;
  const selection = window.getSelection();
  const range = document.createRange();
  range.selectNodeContents(element);
  selection.removeAllRanges();
  selection.addRange(range);
}

async function copyNodeResultOutput(nodeId, button) {
  const node = nodes.find((item) => item.id === nodeId);
  const output = node?.testResult?.output || { ok: null, message: "No output available yet." };
  const outputBlock = button?.closest(".io-block");
  const outputPre = outputBlock?.querySelector("pre");
  const visibleOutput = outputPre?.innerText || outputPre?.textContent;
  const originalText = button?.getAttribute("data-i18n") || "Copy";
  const originalParams = JSON.parse(button?.getAttribute("data-i18n-params") || "{}");
  try {
    await copyTextToClipboard(visibleOutput || compactJson(output));
    if (button) {
      uiText(button, "Copied");
      button.classList.add("copied");
      setTimeout(() => {
        uiText(button, originalText, originalParams);
        button.classList.remove("copied");
      }, 1400);
    }
  } catch {
    selectTextElement(outputPre);
    if (button) {
      uiText(button, "Selected");
      button.classList.add("copied");
      setTimeout(() => {
        uiText(button, originalText, originalParams);
        button.classList.remove("copied");
      }, 1800);
    }
  }
}

function parseJsonText(value) {
  if (typeof value !== "string") return null;
  const text = value.trim();
  if (!text) return null;
  const variants = [text];
  if (text.includes("\\n") || text.includes('\\"') || text.includes("\\t")) {
    variants.push(
      text
        .replace(/\\r/g, "\r")
        .replace(/\\n/g, "\n")
        .replace(/\\t/g, "\t")
        .replace(/\\"/g, '"')
    );
  }
  for (const variant of variants) {
    try {
      return JSON.parse(variant);
    } catch {
      // Try embedded JSON candidates below.
    }
  }
  const candidates = [];
  for (const variant of variants) {
    const firstObject = variant.indexOf("{");
    const lastObject = variant.lastIndexOf("}");
    const firstArray = variant.indexOf("[");
    const lastArray = variant.lastIndexOf("]");
    if (firstObject >= 0 && lastObject > firstObject) candidates.push(variant.slice(firstObject, lastObject + 1));
    if (firstArray >= 0 && lastArray > firstArray) candidates.push(variant.slice(firstArray, lastArray + 1));
    const extractedRows = extractJsonArrayAfterKey(variant, "rows");
    if (extractedRows) candidates.push(`{"rows":${extractedRows}}`);
    const partialRows = extractJsonObjectsAfterKey(variant, "rows");
    if (partialRows.length) candidates.push(`{"rows":[${partialRows.join(",")}]}`);
  }
  for (const candidate of candidates) {
    try {
      return JSON.parse(candidate);
    } catch {
      // Keep trying other embedded JSON candidates.
    }
  }
  try {
    const unescaped = JSON.parse(`"${text.replace(/\\/g, "\\\\").replace(/"/g, '\\"')}"`);
    if (unescaped !== text) return parseJsonText(unescaped);
  } catch {
    // Not an escaped JSON string.
  }
  return null;
}

function extractJsonArrayAfterKey(text, key) {
  const keyIndex = text.indexOf(`"${key}"`);
  if (keyIndex < 0) return null;
  const colonIndex = text.indexOf(":", keyIndex);
  const arrayStart = text.indexOf("[", colonIndex);
  if (colonIndex < 0 || arrayStart < 0) return null;
  let depth = 0;
  let inString = false;
  let escaping = false;
  for (let index = arrayStart; index < text.length; index += 1) {
    const char = text[index];
    if (escaping) {
      escaping = false;
      continue;
    }
    if (char === "\\") {
      escaping = true;
      continue;
    }
    if (char === '"') {
      inString = !inString;
      continue;
    }
    if (inString) continue;
    if (char === "[") depth += 1;
    if (char === "]") {
      depth -= 1;
      if (depth === 0) return text.slice(arrayStart, index + 1);
    }
  }
  return null;
}

function extractJsonObjectsAfterKey(text, key) {
  const keyIndex = text.indexOf(`"${key}"`);
  if (keyIndex < 0) return [];
  const colonIndex = text.indexOf(":", keyIndex);
  const arrayStart = text.indexOf("[", colonIndex);
  if (colonIndex < 0 || arrayStart < 0) return [];
  const objects = [];
  let objectStart = -1;
  let depth = 0;
  let inString = false;
  let escaping = false;
  for (let index = arrayStart + 1; index < text.length; index += 1) {
    const char = text[index];
    if (escaping) {
      escaping = false;
      continue;
    }
    if (char === "\\") {
      escaping = true;
      continue;
    }
    if (char === '"') {
      inString = !inString;
      continue;
    }
    if (inString) continue;
    if (char === "{") {
      if (depth === 0) objectStart = index;
      depth += 1;
    } else if (char === "}") {
      depth -= 1;
      if (depth === 0 && objectStart >= 0) {
        objects.push(text.slice(objectStart, index + 1));
        objectStart = -1;
      }
    } else if (char === "]" && depth === 0) {
      break;
    }
  }
  return objects;
}

function hasPrimaryRows(value) {
  return primaryResultRows(value).length > 0;
}

function tablePayloadFromResult(value, depth = 0) {
  if (depth > 6) return value;
  if (typeof value === "string") {
    const parsed = parseJsonText(value);
    return parsed ? tablePayloadFromResult(parsed, depth + 1) : value;
  }
  if (!isPlainObject(value)) return value;
  if (hasPrimaryRows(value)) return value;
  const unwrapKeys = ["stdout", "body", "output", "result", "payload", "data"];
  for (const key of unwrapKeys) {
    if (!(key in value)) continue;
    const unwrapped = tablePayloadFromResult(value[key], depth + 1);
    if (Array.isArray(unwrapped) || hasPrimaryRows(unwrapped)) return unwrapped;
    if (isPlainObject(unwrapped) && unwrapped !== value[key] && Object.keys(unwrapped).length) return unwrapped;
  }
  return value;
}

function humanizeFieldName(value) {
  return String(value || "")
    .replace(/[_-]+/g, " ")
    .replace(/([a-z])([A-Z])/g, "$1 $2")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function isPlainObject(value) {
  return value && typeof value === "object" && !Array.isArray(value);
}

function shortCellValue(value) {
  if (value === null || value === undefined || value === "") return "";
  if (Array.isArray(value)) return value.length ? `${value.length} items` : "";
  if (isPlainObject(value)) return JSON.stringify(value);
  return String(value);
}

function firstHttpUrl(value) {
  const text = String(value || "").trim();
  const match = text.match(/https?:\/\/[^\s"'<>]+/i);
  return match ? match[0].replace(/[),.;]+$/, "") : "";
}

function renderTableCellValue(value) {
  const text = shortCellValue(value);
  const url = firstHttpUrl(text);
  if (!url) return escapeHtml(text);
  const label = text.length > 72 ? `${text.slice(0, 69)}...` : text;
  return `<a class="result-cell-link" href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer" title="${escapeHtml(url)}">${escapeHtml(label)}</a>`;
}

function flattenRow(row, prefix = "", depth = 0) {
  if (!isPlainObject(row)) return { [prefix || "value"]: row };
  const flat = {};
  Object.entries(row).forEach(([key, value]) => {
    const flatKey = prefix ? `${prefix}.${key}` : key;
    if (value === null || value === undefined || typeof value !== "object") {
      flat[flatKey] = value;
    } else if (Array.isArray(value)) {
      flat[flatKey] = value.length ? `${value.length} items` : "";
      if (value.length && isPlainObject(value[0]) && depth < 2) {
        Object.assign(flat, flattenRow(value[0], `${flatKey}.0`, depth + 1));
      }
    } else if (depth < 3) {
      Object.assign(flat, flattenRow(value, flatKey, depth + 1));
    } else {
      flat[flatKey] = JSON.stringify(value);
    }
  });
  return flat;
}

function primaryResultRows(value) {
  if (!value || typeof value !== "object") return [];
  const preferredKeys = ["rows", "orders", "items", "shipments", "results", "data", "records", "listings"];
  for (const key of preferredKeys) {
    if (Array.isArray(value[key]) && value[key].length) return value[key];
  }
  if (Array.isArray(value)) return value;
  for (const item of Object.values(value)) {
    if (Array.isArray(item) && item.length) return item;
  }
  return [];
}

function summaryRowsFromObject(value) {
  if (!isPlainObject(value)) return [{ Field: "Value", Value: shortCellValue(value) }];
  return Object.entries(value)
    .filter(([, item]) => item === null || item === undefined || typeof item !== "object")
    .map(([key, item]) => ({ Field: humanizeFieldName(key), Value: shortCellValue(item) }));
}

function resultTableModel(value) {
  const tablePayload = tablePayloadFromResult(value);
  const parsedStdout = tablePayload !== value;
  const rows = primaryResultRows(tablePayload);
  if (rows.length) {
    const tableRows = rows.map((row) => flattenRow(row));
    const columns = [...new Set(tableRows.flatMap((row) => Object.keys(row)))].slice(0, 80);
    return {
      columns,
      rows: tableRows.slice(0, 100),
      totalRows: rows.length,
      sourceRows: rows.length,
      parsedStdout,
    };
  }
  if (isPlainObject(value?.outputTable) && Array.isArray(value.outputTable.rows) && value.outputTable.rows.length) {
    return {
      columns: Array.isArray(value.outputTable.columns) ? value.outputTable.columns.slice(0, 80) : [...new Set(value.outputTable.rows.flatMap((row) => Object.keys(row || {})))].slice(0, 80),
      rows: value.outputTable.rows.slice(0, 100),
      totalRows: Number(value.outputTable.totalRows || value.outputTable.rows.length),
      sourceRows: Number(value.outputTable.totalRows || value.outputTable.rows.length),
      parsedStdout: false,
    };
  }
  const tableRows = rows.length ? rows.map(flattenRow) : summaryRowsFromObject(tablePayload);
  const columns = [...new Set(tableRows.flatMap((row) => Object.keys(row)))].slice(0, 80);
  return {
    columns,
    rows: tableRows.slice(0, 100),
    totalRows: tableRows.length,
    sourceRows: rows.length,
    parsedStdout,
  };
}

function normalizeNodeOutput(value) {
  const tablePayload = tablePayloadFromResult(value);
  if (tablePayload !== value && isPlainObject(tablePayload)) {
    return {
      ...tablePayload,
      _raw_runner_output: value,
    };
  }
  return tablePayload;
}

function renderResultTable(value, emptyText = "No table data available yet.") {
  const model = resultTableModel(value);
  if (!model.columns.length || !model.rows.length) {
    return `<div class="result-table-empty">${uiLabel(emptyText)}</div>`;
  }
  const minTableWidth = Math.max(760, model.columns.length * 132);
  return `
    <div class="result-table-shell">
      <div class="result-scroll-hint" ${uiAttrs("Scroll right to see more fields")}>${escapeHtml(agentT("Scroll right to see more fields"))}</div>
      <div class="result-table-wrap">
      <table class="result-data-table" style="min-width:${minTableWidth}px">
        <thead>
          <tr>${model.columns.map((column) => `<th>${escapeHtml(humanizeFieldName(column))}</th>`).join("")}</tr>
        </thead>
        <tbody>
          ${model.rows.map((row) => `
            <tr>${model.columns.map((column) => `<td title="${escapeHtml(shortCellValue(row[column]))}">${renderTableCellValue(row[column])}</td>`).join("")}</tr>
          `).join("")}
        </tbody>
      </table>
      </div>
    </div>
    <div class="result-table-foot">${model.totalRows > model.rows.length ? uiLabel("Showing first {shown} of {total} rows.", { shown: model.rows.length, total: model.totalRows }) : uiLabel(model.totalRows === 1 ? "{count} row shown." : "{count} rows shown.", { count: model.totalRows })}</div>
  `;
}

function workflowOrder() {
  const incoming = links.reduce((map, link) => {
    map[link.to] = (map[link.to] || 0) + 1;
    return map;
  }, {});
  const remaining = new Map(nodes.map((node, index) => [node.id, { node, index }]));
  const ordered = [];

  while (remaining.size) {
    const next = [...remaining.values()]
      .filter(({ node }) => !incoming[node.id])
      .sort((a, b) => a.index - b.index)[0] || [...remaining.values()].sort((a, b) => a.index - b.index)[0];
    ordered.push(next.node);
    remaining.delete(next.node.id);
    for (const link of links.filter((item) => item.from === next.node.id)) {
      incoming[link.to] = Math.max(0, (incoming[link.to] || 0) - 1);
    }
  }

  return ordered;
}

function incomingNodes(node) {
  return links
    .filter((link) => link.to === node.id)
    .map((link) => nodes.find((item) => item.id === link.from))
    .filter(Boolean);
}

function previousNodeOutputs(node) {
  return incomingNodes(node)
    .map((item) => ({ node: item.name, output: item.testResult?.output || null }))
    .filter((item) => item.output);
}

function sourceFieldOptions(node) {
  const outputs = previousNodeOutputs(node).map((item) => item.output);
  const fields = new Set();
  for (const output of outputs) {
    const rows = findExportRows(output);
    const sample = Array.isArray(rows) ? rows[0] : null;
    if (sample && typeof sample === "object") {
      Object.keys(sample).forEach((key) => fields.add(key));
    }
  }
  return [...fields].map((key) => [key, key]);
}

function previousStepPayload(node) {
  const outputs = previousNodeOutputs(node);
  if (!outputs.length) return {};
  return outputs.length === 1 ? outputs[0].output : Object.fromEntries(outputs.map((item) => [item.node, item.output]));
}

function resolvePath(value, path) {
  return String(path || "").split(".").reduce((current, key) => {
    if (key === "previous_step") return current;
    if (current && typeof current === "object") return current[key];
    return undefined;
  }, value);
}

function generateManualGptPrompt(node) {
  const settings = node.integrationSettings || {};
  const previous = previousStepPayload(node);
  const rows = findExportRows(previous) || [];
  const replacements = {
    previous_step: previous,
    "previous_step.rows": rows,
    return_format: settings.returnFormat || {},
  };
  let prompt = settings.promptTemplate || "";
  prompt = prompt.replace(/\{\{\s*([^}]+?)\s*\}\}/g, (_match, key) => {
    const cleanKey = String(key).trim();
    const value = Object.prototype.hasOwnProperty.call(replacements, cleanKey)
      ? replacements[cleanKey]
      : resolvePath(previous, cleanKey);
    return typeof value === "string" ? value : compactJson(value ?? "");
  });
  return `${prompt}\n\nExpected return format:\n${settings.returnFormat || "{}"}`;
}

function parseManualResult(text) {
  const raw = String(text || "").trim();
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch {
    const match = raw.match(/```(?:json)?\s*([\s\S]*?)```/i);
    if (match) {
      try {
        return JSON.parse(match[1]);
      } catch {
        return { raw };
      }
    }
    return { raw };
  }
}

function needsCellXMapping(node) {
  if (node?.type !== "cellx-db") return false;
  const operation = node.integrationSettings?.operation || operationFromCellXNode(node);
  return ["insert", "update", "upsert", "bulk_import"].includes(operation);
}

function renderCellXMappingBuilder(node) {
  if (!needsCellXMapping(node)) return "";
  const sourceOptions = sourceFieldOptions(node);
  const targetOptions = cellxColumnOptions(node);
  const sourceMarkup = sourceOptions.length
    ? sourceOptions.map(([value, text]) => `<option value="${escapeHtml(value)}">${escapeHtml(text)}</option>`).join("")
    : `<option value="" ${uiAttrs("Run previous node first")}>${escapeHtml(agentT("Run previous node first"))}</option>`;
  const targetMarkup = targetOptions.length
    ? targetOptions.map(([value, text]) => `<option value="${escapeHtml(value)}">${escapeHtml(text)}</option>`).join("")
    : `<option value="" ${uiAttrs("Choose a table first")}>${escapeHtml(agentT("Choose a table first"))}</option>`;
  return `
    <div class="mapping-builder">
      <div class="mapping-title">
        <strong ${uiAttrs("Field Map Builder")}>${escapeHtml(agentT("Field Map Builder"))}</strong>
        <span ${uiAttrs("Map previous result fields into the selected CellX table.")}>${escapeHtml(agentT("Map previous result fields into the selected CellX table."))}</span>
      </div>
      <div class="mapping-row">
        <label>${uiLabel("Source Field")}<select id="sourceFieldSelect">${sourceMarkup}</select></label>
        <label>${uiLabel("CellX Field")}<select id="targetFieldSelect">${targetMarkup}</select></label>
      </div>
      <button id="addMappingBtn" type="button" ${uiAttrs("Add Mapping")}>${escapeHtml(agentT("Add Mapping"))}</button>
    </div>
  `;
}

function renderManualHandoffTools(node) {
  if (node?.type !== "ai" || node.integrationSettings?.authMode !== "manual_web_handoff") return "";
  return `
    <div class="manual-handoff-tools">
      <button id="copyGptPromptBtn" class="primary" type="button" ${uiAttrs("Copy GPT Prompt")}>${escapeHtml(agentT("Copy GPT Prompt"))}</button>
      <button id="openChatGptBtn" type="button" ${uiAttrs("Open ChatGPT")}>${escapeHtml(agentT("Open ChatGPT"))}</button>
    </div>
  `;
}

function buildNodeTestInput(node) {
  const previous = links
    .filter((link) => link.to === node.id)
    .map((link) => nodes.find((item) => item.id === link.from)?.name)
    .filter(Boolean);
  const base = {
    node: node.name,
    type: node.type,
    action: node.action,
    from: previous.length ? previous : ["sample_order_event"],
  };
  if (node.type === "trigger") {
    base.sampleEvent = { order_id: "CX-10042", payment_status: "Captured", total: 128.9 };
  } else if (node.type === "condition") {
    base.expression = node.action || "payment_status == Captured";
    base.value = "Captured";
  } else if (node.type === "ai") {
    if (node.integrationSettings?.authMode === "manual_web_handoff") {
      base.handoff = "manual_chatgpt";
      base.chatUrl = node.integrationSettings?.chatUrl || "https://chatgpt.com/";
      base.previousOutput = previousStepPayload(node);
      base.prompt = generateManualGptPrompt(node);
    } else {
      base.prompt = "Classify order risk and recommend fulfillment route.";
    }
  } else if (node.type === "carrier") {
    base.package = { weight_lb: 2.4, destination: "CA 92660" };
  } else if (node.name === "Google Sheets" || String(node.action || "").includes("/google/sheets")) {
    base.spreadsheetId = node.integrationSettings?.spreadsheetId || "";
    base.sheetName = node.integrationSettings?.sheetName || "";
    base.appendMode = node.integrationSettings?.appendMode || "append_rows";
    base.inputPayload = node.integrationSettings?.inputPayload || "{{previous_step.rows}}";
    base.fieldMapping = node.integrationSettings?.fieldMapping || "";
    base.previousOutput = previousStepPayload(node);
  } else if (node.type === "action") {
    base.update = { order_id: "CX-10042", status: "Ready to fulfill" };
  } else if (node.type === "script") {
    base.scriptName = node.integrationSettings?.scriptName || "amazon_bestsellers_demo.py";
    try {
      base.payload = JSON.parse(node.integrationSettings?.inputJson || "{}");
    } catch {
      base.payload = node.integrationSettings?.inputJson || "";
    }
  } else if (node.type === "external-agent") {
    base.agentName = node.integrationSettings?.agentName || node.name;
    base.runLocation = node.integrationSettings?.runLocation || "customer_private";
    base.runnerName = node.integrationSettings?.runnerName || "";
    base.connectionType = node.integrationSettings?.connectionType || "api";
    base.endpointUrl = node.integrationSettings?.endpointUrl || "";
    base.repoUrl = node.integrationSettings?.repoUrl || "";
    base.branch = node.integrationSettings?.branch || "";
    base.installCommand = node.integrationSettings?.installCommand || "";
    base.runCommand = node.integrationSettings?.runCommand || "";
    base.secretEnvNames = node.integrationSettings?.secretEnvNames || "";
    base.refreshRepo = node.integrationSettings?.refreshRepo || "false";
    base.method = node.integrationSettings?.method || "POST";
    base.authType = node.integrationSettings?.authType || "none";
    base.executeLive = node.integrationSettings?.executeLive || "false";
    base.inputMapping = node.integrationSettings?.inputMapping || "";
    base.previousOutput = previousStepPayload(node);
  } else if (node.type === "cellx-db") {
    const rows = findExportRows(previousNodeOutputs(node)[0]?.output);
    base.operation = node.integrationSettings?.operation || operationFromCellXNode(node);
    base.tableName = node.integrationSettings?.tableName || "";
    base.inputPayload = node.integrationSettings?.inputPayload || "{{previous_step.rows}}";
    base.fieldMapping = node.integrationSettings?.fieldMapping || "";
    base.previousRows = Array.isArray(rows) ? rows.length : 0;
  } else if (node.name === "JSON Transform" || String(node.action || "").includes("/json-transform")) {
    base.sourcePath = node.integrationSettings?.sourcePath || "previous_step";
    base.transformMapping = node.integrationSettings?.transformMapping || "";
    base.outputMode = node.integrationSettings?.outputMode || "object";
    base.previousOutput = previousStepPayload(node);
  } else if (node.type === "communication") {
    base.deliveryMode = node.integrationSettings?.deliveryMode || "preview";
    base.to = node.integrationSettings?.to || "";
    base.subjectTemplate = node.integrationSettings?.subjectTemplate || "";
    base.bodyTemplate = node.integrationSettings?.bodyTemplate || "";
    base.previousOutput = previousStepPayload(node);
  }
  return base;
}

function buildNodeTestOutput(node, status, message, result = null) {
  if (result?.output && node.type !== "condition" && node.type !== "carrier") return normalizeNodeOutput(result.output);
  if (status === "error") {
    return normalizeNodeOutput(result?.output || result?.error || { ok: false, message });
  }
  if (node.type === "trigger") {
    return { ok: true, emitted: "order.created", order_id: "CX-10042" };
  }
  if (node.type === "condition") {
    if (/switch/i.test(node.name || "")) return buildCarrierSwitchOutput(node);
    return { ok: true, branch: "paid_order", matched: true };
  }
  if (node.type === "ai") {
    if (node.integrationSettings?.authMode === "manual_web_handoff") {
      const pasted = parseManualResult(node.integrationSettings?.manualResult);
      if (pasted) {
        return {
          ok: true,
          mode: "manual_web_handoff",
          source: "pasted_gpt_result",
          result: pasted,
        };
      }
      return {
        ok: true,
        mode: "manual_web_handoff",
        chatUrl: node.integrationSettings?.chatUrl || "https://chatgpt.com/",
        prompt: generateManualGptPrompt(node),
        expectedReturnFormat: node.integrationSettings?.returnFormat || "{}",
        nextStep: "Copy this prompt into ChatGPT, then paste ChatGPT's JSON response into Pasted GPT Result and run Connect / Test again.",
      };
    }
    return { ok: true, risk: "low", recommendation: "send_to_carrier_rate_step" };
  }
  if (node.type === "carrier") {
    return buildCarrierShipmentOutput(node);
  }
  if (node.type === "action") {
    return { ok: true, wrote: "cx_order.status", value: "Ready to fulfill" };
  }
  if (node.type === "log") {
    return { ok: true, logged: "cx_workflow_log", event: "workflow.test.completed" };
  }
  if (node.type === "script") {
    return { ok: true, script: node.integrationSettings?.scriptName || "customer script", message: message || "Script completed." };
  }
  if (node.type === "external-agent") {
    return {
      ok: true,
      agent: node.integrationSettings?.agentName || node.name,
      mode: node.integrationSettings?.connectionType || "api",
      message: message || "External agent connector is ready.",
      dryRun: String(node.integrationSettings?.executeLive || "false") !== "true",
    };
  }
  return { ok: true, message: message || "Step test completed." };
}

function firstObjectWithCarrierRows(node) {
  for (const item of previousNodeOutputs(node)) {
    const output = item?.output || item;
    if (output && typeof output === "object" && (Array.isArray(output.ups_rows) || Array.isArray(output.fedex_rows) || Array.isArray(output.manual_review_rows))) {
      return output;
    }
  }
  return {};
}

function buildCarrierSwitchOutput(node) {
  const routed = firstObjectWithCarrierRows(node);
  const upsRows = Array.isArray(routed.ups_rows) ? routed.ups_rows : [];
  const fedexRows = Array.isArray(routed.fedex_rows) ? routed.fedex_rows : [];
  const manualRows = Array.isArray(routed.manual_review_rows) ? routed.manual_review_rows : [];
  return {
    ok: true,
    rule: "carrier",
    total_orders: Number(routed.row_count || routed.orders_count || upsRows.length + fedexRows.length + manualRows.length || 0),
    routes: [
      { carrier: "UPS", count: upsRows.length, next_step: "UPS Shipment" },
      { carrier: "FEDEX", count: fedexRows.length, next_step: "FedEx Shipment" },
      { carrier: "MANUAL_REVIEW", count: manualRows.length, next_step: "Manual Review List" },
    ],
    note: "Orders are routed by detected requested shipping/carrier values from Order Desk.",
  };
}

function buildCarrierShipmentOutput(node) {
  const routed = firstObjectWithCarrierRows(node);
  const carrier = /fedex/i.test(node.name || "") ? "FEDEX" : /ups/i.test(node.name || "") ? "UPS" : "CARRIER";
  const rows = carrier === "UPS" ? (routed.ups_rows || []) : carrier === "FEDEX" ? (routed.fedex_rows || []) : [];
  return {
    ok: true,
    carrier,
    dry_run: true,
    shipment_payload_count: rows.length,
    sample_payload: rows[0]?.carrier_payload || null,
    next_step: rows.length ? `Connect ${carrier} credentials to rate or create labels.` : `No ${carrier} orders in the current batch.`,
  };
}

function summarizeResultPayload(output) {
  if (!output || typeof output !== "object") return [];
  const rows = [];
  if ("orders_count" in output) rows.push(["Orders fetched", output.orders_count, true]);
  if ("row_count" in output) rows.push(["Rows", output.row_count, true]);
  if ("ups_count" in output) rows.push(["UPS", output.ups_count, true]);
  if ("fedex_count" in output) rows.push(["FedEx", output.fedex_count, true]);
  if ("manual_review_count" in output) rows.push(["Manual review", output.manual_review_count, true]);
  if ("shipment_payload_count" in output) rows.push(["Shipment payloads", output.shipment_payload_count, true]);
  if (Array.isArray(output.routes)) {
    output.routes.forEach((route) => rows.push([route.carrier, route.count]));
  }
  if (output.message) rows.push(["Message", output.message, true]);
  if (output.note) rows.push(["Note", output.note, true]);
  return rows;
}

function showNodeResultDialog(nodeId) {
  const node = nodes.find((item) => item.id === nodeId);
  if (!node) return;
  const result = node.testResult || {
    status: "pending",
    message: "Not tested yet.",
    input: buildNodeTestInput(node),
    output: { ok: null, message: "Click Test Selected or Run Agent first." },
  };
  document.getElementById("resultDialog")?.remove();
  const summary = summarizeResultPayload(result.output || {});
  const tableModel = resultTableModel(result.output || {});
  const dialog = document.createElement("div");
  dialog.id = "resultDialog";
  dialog.className = "result-dialog-backdrop";
  dialog.innerHTML = `
    <section class="result-dialog" role="dialog" aria-modal="true" aria-labelledby="resultDialogTitle">
      <header>
        <div>
          <strong id="resultDialogTitle">${escapeHtml(node.name)}</strong>
          <span>${uiLabel(result.message || "Workflow node result")}</span>
        </div>
        <button type="button" data-close-result-dialog ${uiAttrs("Close")}>${escapeHtml(agentT("Close"))}</button>
      </header>
      ${summary.length ? `
        <div class="result-summary">
          ${summary.map(([label, value, chrome]) => `<div><span>${chrome ? uiLabel(label) : escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`).join("")}
        </div>
      ` : ""}
      <div class="result-dialog-table">
        <div class="result-dialog-section-title">
          <b ${uiAttrs("Output Table")}>${escapeHtml(agentT("Output Table"))}</b>
          <span>${tableModel.sourceRows ? uiLabel("{count} source rows detected", { count: tableModel.sourceRows }) : uiLabel(tableModel.parsedStdout ? "Parsed stdout JSON" : "Summary fields")}</span>
        </div>
        ${renderResultTable(result.output || {})}
      </div>
      <div class="result-dialog-grid">
        <div>
          <b ${uiAttrs("Input")}>${escapeHtml(agentT("Input"))}</b>
          <pre>${escapeHtml(compactJson(result.input || {}))}</pre>
        </div>
        <div class="io-block">
          <div class="io-title-row">
            <b ${uiAttrs("Output")}>${escapeHtml(agentT("Output"))}</b>
            <button type="button" data-copy-node-output="${escapeHtml(node.id)}" ${uiAttrs("Copy")}>${escapeHtml(agentT("Copy"))}</button>
          </div>
          <pre>${escapeHtml(compactJson(result.output || {}))}</pre>
        </div>
      </div>
    </section>
  `;
  dialog.addEventListener("click", (event) => {
    if (event.target === dialog || event.target.closest("[data-close-result-dialog]")) dialog.remove();
  });
  document.addEventListener("keydown", function closeOnEsc(event) {
    if (event.key === "Escape") {
      dialog.remove();
      document.removeEventListener("keydown", closeOnEsc);
    }
  });
  document.body.appendChild(dialog);
}

function renderWorkflowResultTabs() {
  const orderedNodes = workflowOrder();
  if (!orderedNodes.length) return "";
  if (!activeResultNodeId || !orderedNodes.some((node) => node.id === activeResultNodeId)) {
    activeResultNodeId = orderedNodes[0].id;
  }
  const activeNode = orderedNodes.find((node) => node.id === activeResultNodeId) || orderedNodes[0];
  const result = activeNode.testResult || {
    status: "pending",
    message: "Not tested yet.",
    input: buildNodeTestInput(activeNode),
    output: { ok: null, message: "Click Test Selected or Run Agent first." },
  };
  return `
    <div class="canvas-result-tabs-shell">
      <strong ${uiAttrs("Results")}>${escapeHtml(agentT("Results"))}</strong>
      <div class="canvas-result-tabs" role="tablist" data-agent-i18n-attributes data-i18n-aria-label="Workflow step results" aria-label="${escapeHtml(agentT("Workflow step results"))}">
        ${orderedNodes.map((node, index) => {
          const nodeResult = node.testResult || { status: "pending" };
          const status = nodeResult.status || "pending";
          const rowCount = resultTableModel(nodeResult.output || {}).totalRows;
          return `
            <button type="button" class="${node.id === activeNode.id ? "active" : ""}" data-result-tab="${escapeHtml(node.id)}" title="${index + 1}. ${escapeHtml(node.name)}">
              <span class="result-step-number ${escapeHtml(status)}">${index + 1}</span>
              <b>${escapeHtml(node.name)}</b>
              <em class="${escapeHtml(status)}">${rowCount ? uiLabel("{count} rows", { count: rowCount }) : testBadgeLabel(status)}</em>
            </button>
          `;
        }).join("")}
      </div>
    </div>
  `;
}

function renderWorkflowResultTablePanel() {
  const orderedNodes = workflowOrder();
  if (!orderedNodes.length) return "";
  if (!activeResultNodeId || !orderedNodes.some((node) => node.id === activeResultNodeId)) {
    activeResultNodeId = orderedNodes[0].id;
  }
  const activeNode = orderedNodes.find((node) => node.id === activeResultNodeId) || orderedNodes[0];
  const result = activeNode.testResult || {
    status: "pending",
    message: "Not tested yet.",
    input: buildNodeTestInput(activeNode),
    output: { ok: null, message: "Click Test Selected or Run Agent first." },
  };
  return `
    <div class="canvas-result-panel">
      <div class="result-tab-panel-head">
        <div>
          <strong>${escapeHtml(activeNode.name)}</strong>
          <span>${uiLabel(result.message || "Workflow step result")}</span>
        </div>
        <button type="button" data-view-node-result="${escapeHtml(activeNode.id)}" ${uiAttrs("View Full Result")}>${escapeHtml(agentT("View Full Result"))}</button>
      </div>
      ${renderResultTable(result.output || {}, "Run this workflow step to see rows and columns.")}
    </div>
  `;
}

function renderNodeTestResults() {
  if (!nodes.length) {
    return `<div class="test-results empty" ${uiAttrs("No workflow nodes to test.")}>${escapeHtml(agentT("No workflow nodes to test."))}</div>`;
  }
  return `
    <section id="nodeTestResults" class="test-results">
      <div class="test-results-title">
        <strong ${uiAttrs("Node Test Results")}>${escapeHtml(agentT("Node Test Results"))}</strong>
        <span ${uiAttrs("Input and Output for each workflow node")}>${escapeHtml(agentT("Input and Output for each workflow node"))}</span>
      </div>
      ${workflowOrder().map((node, index) => {
        const result = node.testResult || {
          status: "pending",
          message: "Not tested yet.",
          input: buildNodeTestInput(node),
          output: { ok: null, message: "Click Connect / Test to run this node." },
        };
        return `
          <article class="test-result-card ${result.status}">
            <div class="test-result-head">
              <strong>${index + 1}. ${escapeHtml(node.name)}</strong>
              <span>
                <button type="button" data-view-node-result="${escapeHtml(node.id)}" ${uiAttrs("View Result")}>${escapeHtml(agentT("View Result"))}</button>
                <em>${testBadgeLabel(result.status)}</em>
              </span>
            </div>
            <p>${uiLabel(result.message || "")}</p>
            <div class="io-grid">
              <div>
                <b ${uiAttrs("Input")}>${escapeHtml(agentT("Input"))}</b>
                <pre>${escapeHtml(compactJson(result.input || {}))}</pre>
              </div>
              <div class="io-block">
                <div class="io-title-row">
                  <b ${uiAttrs("Output")}>${escapeHtml(agentT("Output"))}</b>
                  <button type="button" data-copy-node-output="${escapeHtml(node.id)}" ${uiAttrs("Copy")}>${escapeHtml(agentT("Copy"))}</button>
                </div>
                <pre>${escapeHtml(compactJson(result.output || {}))}</pre>
              </div>
            </div>
          </article>
        `;
      }).join("")}
    </section>
  `;
}

function dailyCronToTime(expression) {
  const match = String(expression || "").trim().match(/^(\d{1,2})\s+(\d{1,2})\s+\*\s+\*\s+\*$/);
  if (!match || Number(match[1]) > 59 || Number(match[2]) > 23) return "";
  return `${match[2].padStart(2, "0")}:${match[1].padStart(2, "0")}`;
}

function dailyTimeToCron(value) {
  const match = String(value || "").match(/^(\d{2}):(\d{2})$/);
  if (!match || Number(match[1]) > 23 || Number(match[2]) > 59) return "";
  return `${Number(match[2])} ${Number(match[1])} * * *`;
}

function renderDailyTimeField(node) {
  const cron = String(node.integrationSettings.schedule || "");
  const time = dailyCronToTime(cron);
  return `<div class="daily-time-field">
    <label class="integration-field">${uiLabel("Daily Run Time")}<b class="required-mark" ${uiAttrs("Required")}>${escapeHtml(agentT("Required"))}</b>
      <input type="time" data-daily-run-time value="${time}" step="60" aria-describedby="dailyCronStatus">
    </label>
    <p id="dailyCronStatus" class="daily-cron-status" ${time ? "hidden" : ""} ${uiAttrs("Custom cron retained. The daily scheduler requires one daily run time.")}>${escapeHtml(agentT("Custom cron retained. The daily scheduler requires one daily run time."))}</p>
    <details class="daily-cron-advanced" ${time ? "" : "open"}>
      <summary ${uiAttrs("Advanced Cron")}>${escapeHtml(agentT("Advanced Cron"))}</summary>
      <label class="integration-field">${uiLabel("Cron Expression")}
        <input type="text" data-integration-key="schedule" value="${escapeHtml(cron)}" spellcheck="false">
      </label>
    </details>
  </div>`;
}

function renderIntegrationFields(node) {
  if (!propIntegration || !node) return;
  const spec = ensureIntegrationSettings(node);
  const fields = visibleIntegrationFields(spec, node);
  const requiredKeys = new Set(requiredIntegrationFields(spec, node));
  propIntegration.innerHTML = `
    <div class="integration-title">
      <strong>${uiIntegrationTitle(spec, node)}</strong>
      <span>${uiLabel(spec.summary)}</span>
    </div>
    ${fields.map(({ key, label, type, placeholder, options }) => type === "daily-time" ? renderDailyTimeField(node) : `
      <label class="integration-field">
        ${/^[A-Z][A-Z0-9]*_[A-Z0-9_]+$/.test(label) ? escapeHtml(label) : uiLabel(label)}${requiredKeys.has(key) ? `<b class="required-mark" ${uiAttrs("Required")}>${escapeHtml(agentT("Required"))}</b>` : `<b class="optional-mark" ${uiAttrs("Optional")}>${escapeHtml(agentT("Optional"))}</b>`}
        ${type === "select" ? `
          <select data-integration-key="${key}">
            ${(options || []).map(([value, text]) => `<option value="${value}"${node.integrationSettings[key] === value ? " selected" : ""} ${(["tableName", "timezone", "method"].includes(key) || ["STARTTLS", "SSL"].includes(text)) ? "" : uiAttrs(text)}>${escapeHtml((["tableName", "timezone", "method"].includes(key) || ["STARTTLS", "SSL"].includes(text)) ? text : agentT(text))}</option>`).join("")}
          </select>
        ` : type === "textarea" ? `
          <textarea data-integration-key="${key}" rows="4" ${uiPlaceholder(placeholder)}>${node.integrationSettings[key] || ""}</textarea>
        ` : `
          <input data-integration-key="${key}" type="${type}" value="${node.integrationSettings[key] || ""}" ${uiPlaceholder(placeholder)}>
        `}
      </label>
    `).join("")}
    ${renderCellXMappingBuilder(node)}
    ${renderManualHandoffTools(node)}
    ${node.type === "trigger" && node.action === "cron" ? scheduleStatusMarkup() : ""}
    ${integrationStatusMarkup(node.connection)}
    ${renderNodeTestResults()}
    <p class="secret-note" ${uiAttrs("Secrets should be stored on the backend or a secret manager. This designer keeps placeholders only.")}>${escapeHtml(agentT("Secrets should be stored on the backend or a secret manager. This designer keeps placeholders only."))}</p>
  `;
  renderPropertyActionBar(node);
  document.getElementById("refreshScheduleBtn")?.addEventListener("click", async () => {
    const workflowId = activeWorkflowId;
    try {
      const data = await workflowManagementFetch(`/workflow-schedules?id=${encodeURIComponent(workflowId)}`, { cache: "no-store" });
      workflowScheduleStatuses.set(workflowId, data);
      if (activeWorkflowId === workflowId && selectedId === node.id) renderIntegrationFields(node);
    } catch (error) {
      alert(agentT(error.message || "Could not load schedule status."));
    }
  });
  const dailyTimeInput = propIntegration.querySelector("[data-daily-run-time]");
  const updateDailyTime = () => {
    const cron = dailyTimeToCron(dailyTimeInput.value);
    dailyTimeInput.dataset.edited = "true";
    dailyTimeInput.setCustomValidity(cron ? "" : agentT("Choose a valid daily run time."));
    const current = nodes.find(item => item.id === selectedId);
    if (!cron || !current) return;
    current.integrationSettings.schedule = cron;
    current.connection = null;
    propIntegration.querySelector('[data-integration-key="schedule"]').value = cron;
    propIntegration.querySelector("#dailyCronStatus").hidden = true;
  };
  dailyTimeInput?.addEventListener("input", updateDailyTime);
  dailyTimeInput?.addEventListener("change", updateDailyTime);
  propIntegration.querySelectorAll("[data-integration-key]").forEach((input) => {
    const updateSetting = () => {
      const current = nodes.find((item) => item.id === selectedId);
      if (!current) return;
    current.integrationSettings = current.integrationSettings || {};
    current.integrationSettings[input.dataset.integrationKey] = input.value;
      if (input.dataset.integrationKey === "schedule" && dailyTimeInput) {
        dailyTimeInput.value = dailyCronToTime(input.value);
        dailyTimeInput.dataset.edited = "false";
        dailyTimeInput.setCustomValidity("");
        propIntegration.querySelector("#dailyCronStatus").hidden = Boolean(dailyTimeInput.value);
      }
      current.connection = null;
      if (input.dataset.integrationKey === "authMode") {
        renderIntegrationFields(current);
      }
      if (input.dataset.integrationKey === "operation" || input.dataset.integrationKey === "tableName") {
        renderIntegrationFields(current);
      }
    };
    input.addEventListener("input", updateSetting);
    input.addEventListener("change", updateSetting);
  });
  document.getElementById("addMappingBtn")?.addEventListener("click", () => {
    const current = nodes.find((item) => item.id === selectedId);
    const source = document.getElementById("sourceFieldSelect")?.value;
    const target = document.getElementById("targetFieldSelect")?.value;
    if (!current || !source || !target) return;
    current.integrationSettings = current.integrationSettings || {};
    const line = `${target} <- {{item.${source}}}`;
    const existing = String(current.integrationSettings.fieldMapping || "").trim();
    current.integrationSettings.fieldMapping = existing ? `${existing}\n${line}` : line;
    current.connection = null;
    renderIntegrationFields(current);
    render();
  });
  document.getElementById("copyGptPromptBtn")?.addEventListener("click", async () => {
    const current = nodes.find((item) => item.id === selectedId);
    if (!current) return;
    const prompt = generateManualGptPrompt(current);
    try {
      await navigator.clipboard.writeText(prompt);
      current.connection = { status: "success", message: "GPT prompt copied. Paste it into ChatGPT, then paste the JSON reply back here." };
    } catch {
      current.connection = { status: "manual", message: "Copy from the generated prompt in Node Test Results." };
      current.testResult = {
        status: "manual",
        message: "Clipboard was not available. Copy this prompt manually.",
        input: buildNodeTestInput(current),
        output: { prompt },
      };
    }
    renderIntegrationFields(current);
    render();
  });
  document.getElementById("openChatGptBtn")?.addEventListener("click", () => {
    const current = nodes.find((item) => item.id === selectedId);
    const url = current?.integrationSettings?.chatUrl || "https://chatgpt.com/";
    window.open(url, "_blank", "noopener,noreferrer");
  });
  bindResultViewButtons();
}

function renderPropertyActionBar(node) {
  if (!propertyActionBar) return;
  if (!node) {
    propertyActionBar.innerHTML = "";
    return;
  }
  propertyActionBar.innerHTML = `
    <div class="connection-actions property-actions">
      <button id="testConnectionBtn" class="primary" type="button" ${uiAttrs("Test Selected")}>${escapeHtml(agentT("Test Selected"))}</button>
      <button id="runWorkflowBtn" type="button" ${uiAttrs("Run Agent")}>${escapeHtml(agentT("Run Agent"))}</button>
      <button id="exportResultsBtn" type="button" ${uiAttrs("Export Results")}>${escapeHtml(agentT("Export Results"))}</button>
      <button id="saveCredentialBtn" type="button" ${uiAttrs("Save Config")}>${escapeHtml(agentT("Save Config"))}</button>
      ${nodes.some(item => item.action === "/ext-api/instagram/run") ? `<button id="stopInstagramBtn" type="button" ${uiAttrs("Stop Instagram")}>${escapeHtml(agentT("Stop Instagram"))}</button><a href="http://127.0.0.1:3001/agent/" target="_blank" rel="noopener" ${uiAttrs("Open Local Edition")}>${escapeHtml(agentT("Open Local Edition"))}</a>` : ""}
    </div>
  `;
  document.getElementById("testConnectionBtn")?.addEventListener("click", () => testSelectedIntegration());
  document.getElementById("runWorkflowBtn")?.addEventListener("click", () => testWorkflowIntegrations());
  document.getElementById("stopInstagramBtn")?.addEventListener("click", async () => {
    const response = await fetch(`${apiBase}/instagram/stop`, { method: "POST", headers: aiVoiceHeaders(), body: "{}" });
    const result = await response.json();
    alert(agentT(result.message || "Stop requested."));
  });
  document.getElementById("exportResultsBtn")?.addEventListener("click", () => exportWorkflowResults());
  document.getElementById("saveCredentialBtn")?.addEventListener("click", async () => {
    const current = nodes.find((item) => item.id === selectedId);
    if (!current) return;
    persistNodeConfig(current);
    saveWorkflowDraft();
    try {
      const message = await saveActiveSchedule();
      current.connection = { status: "success", message: message || "Configuration saved in this browser for this workflow step." };
    } catch (error) {
      current.connection = { status: "error", message: uiMessage("Saved locally, but server schedule was not updated: {message}", { message: error.message }) };
    }
    renderIntegrationFields(current);
    render();
  });
}

function bindResultViewButtons() {
  document.querySelectorAll("[data-view-node-result]").forEach((button) => {
    if (button.dataset.boundViewResult === "true") return;
    button.dataset.boundViewResult = "true";
    button.addEventListener("click", () => showNodeResultDialog(button.dataset.viewNodeResult));
  });
  document.querySelectorAll("[data-result-tab]").forEach((button) => {
    if (button.dataset.boundResultTab === "true") return;
    button.dataset.boundResultTab = "true";
    button.addEventListener("click", () => {
      activeResultNodeId = button.dataset.resultTab;
      renderWorkflowResultArea();
      bindResultViewButtons();
      showNodeResultDialog(activeResultNodeId);
    });
  });
}

function renderWorkflowResultArea() {
  if (workflowResultTabsHost) workflowResultTabsHost.innerHTML = renderWorkflowResultTabs();
}

async function loadJson(path) {
  const response = await fetch(`${apiBase}${path}`, { headers: { Accept: "application/json" } });
  if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
  return response.json();
}

async function postJson(path, payload) {
  const response = await fetch(`${apiBase}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json", ...(payload.action === "/ext-api/instagram/run" ? aiVoiceHeaders() : {}) },
    body: JSON.stringify(payload),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(data.message || `${response.status} ${response.statusText}`);
    error.data = data;
    throw error;
  }
  return data;
}

function findExportRows(value) {
  if (!value) return null;
  if (typeof value === "string") {
    const parsed = parseJsonText(value);
    return parsed ? findExportRows(parsed) : null;
  }
  if (Array.isArray(value)) {
    return value.length ? value : null;
  }
  if (typeof value !== "object") return null;
  if (Array.isArray(value.rows) && value.rows.length) return value.rows;
  if (Array.isArray(value.items) && value.items.length) return value.items;
  for (const key of ["stdout", "body", "output", "result", "payload", "data"]) {
    if (!(key in value)) continue;
    const found = findExportRows(value[key]);
    if (found) return found;
  }
  for (const [key, item] of Object.entries(value)) {
    if (key === "outputTable") continue;
    const found = findExportRows(item);
    if (found) return found;
  }
  return null;
}

function collectWorkflowExportRows() {
  for (const node of workflowOrder()) {
    const rows = findExportRows(node.testResult?.output);
    if (rows) return { rows, sourceNode: node };
  }
  return { rows: [], sourceNode: null };
}

async function exportWorkflowResults() {
  const current = nodes.find((item) => item.id === selectedId) || nodes[0];
  const { rows, sourceNode } = collectWorkflowExportRows();
  if (!rows.length) {
    if (current) {
      current.connection = { status: "error", message: "Run Connect / Test first, then export rows from the test output." };
      renderIntegrationFields(current);
      render();
    }
    return;
  }

  const fileName = `${(sourceNode?.name || "cellx-workflow-results").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "cellx-workflow-results"}.xlsx`;
  if (current) {
    current.connection = { status: "testing", message: uiMessage("Exporting {count} rows to Excel...", { count: rows.length }) };
    renderIntegrationFields(current);
  }

  try {
    const response = await fetch(`${apiBase}/results/export`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ rows, fileName, sheetName: sourceNode?.name || "Results" }),
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.message || "Could not export results.");
    }
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = fileName;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
    if (current) current.connection = { status: "success", message: uiMessage("Exported {count} rows to {name}.", { count: rows.length, name: fileName }) };
  } catch (error) {
    if (current) current.connection = { status: "error", message: error.message || "Could not export results." };
  }
  if (current) {
    renderIntegrationFields(current);
    render();
  }
}

async function testNodeIntegration(node, execute = false) {
  if (window.WorkflowVideo?.isNode(node)) return window.WorkflowVideo.test(node);
  if (window.WorkflowPhotos?.isNode(node)) {
    return window.WorkflowPhotos.test(node);
  }
  const spec = ensureIntegrationSettings(node);
  const required = requiredIntegrationFields(spec, node);
  const missing = required.filter((key) => !String(node.integrationSettings[key] || "").trim());
  const input = buildNodeTestInput(node);

  if (missing.length) {
    const message = uiMessage("Missing required fields: {fields}", { fields: missing.join(", ") });
    node.connection = { status: "error", message };
    node.testResult = { status: "error", message, input, output: buildNodeTestOutput(node, "error", message) };
    return;
  }

  try {
    const result = await postJson("/integrations/test", {
      nodeName: node.name,
      nodeType: node.type,
      action: node.action,
      settings: node.integrationSettings,
      previousOutputs: previousNodeOutputs(node),
      required,
      execute: node.action === "/ext-api/instagram/run" && execute,
    });
    const status = result.status || "success";
    const message = result.message || "Connection test passed.";
    node.connection = { status, message };
    node.testResult = { status, message, input: result.input || input, output: buildNodeTestOutput(node, status, message, result) };
  } catch (error) {
    const data = error.data || {};
    const message = data.message || error.message || "Connection test failed.";
    node.connection = { status: "error", message };
    node.testResult = { status: "error", message, input: data.input || input, output: buildNodeTestOutput(node, "error", message, data) };
  }
}

async function testSelectedIntegration() {
  const node = nodes.find((item) => item.id === selectedId);
  if (!node) return;
  const button = document.getElementById("testConnectionBtn");
  if (button) {
    button.disabled = true;
    uiText(button, "Running...");
  }
  node.connection = { status: "testing", message: "Testing selected node..." };
  node.testResult = {
    status: "testing",
    message: "Testing selected node...",
    input: buildNodeTestInput(node),
    output: { ok: null, message: "Testing..." },
  };
  renderIntegrationFields(node);
  render();
  await testNodeIntegration(node);
  renderIntegrationFields(node);
  render();
  document.getElementById("nodeTestResults")?.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

async function testWorkflowIntegrations() {
  if (!nodes.length) return;
  if (dailyTrigger() && nodes.every(node => ["trigger", "script", "cellx-db", "log"].includes(node.type) || (node.type === "tool" && String(node.action).includes("json-transform")))) {
    return runServerWorkflow();
  }
  const selected = nodes.find((item) => item.id === selectedId) || nodes[0];
  const button = document.getElementById("runWorkflowBtn");
  if (button) {
    button.disabled = true;
    uiText(button, "Running...");
  }
  for (const node of nodes) {
    node.connection = { status: "testing", message: "Waiting for workflow test..." };
    node.testResult = {
      status: "testing",
      message: "Queued for test run.",
      input: buildNodeTestInput(node),
      output: { ok: null, message: "Waiting..." },
    };
  }
  renderIntegrationFields(selected);
  render();

  for (const node of workflowOrder()) {
    node.connection = { status: "testing", message: "Checking required credentials..." };
    node.testResult = {
      status: "testing",
      message: "Checking required credentials...",
      input: buildNodeTestInput(node),
      output: { ok: null, message: "Testing..." },
    };
    renderIntegrationFields(selected);
    render();
    await testNodeIntegration(node, true);
    if (window.WorkflowVideo?.isNode(node)) {
      window.WorkflowVideo.pauseFollowing(node);
      break;
    }
    if (node.action === "/ext-api/instagram/run" && node.connection?.status === "error") break;
  }

  renderIntegrationFields(selected);
  render();
  document.getElementById("nodeTestResults")?.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

async function runServerWorkflow() {
  const workflowId = activeWorkflowId;
  const runNodes = nodes;
  const selected = nodes.find(node => node.id === selectedId) || nodes[0];
  ensureIntegrationSettings(dailyTrigger());
  const button = document.getElementById("runWorkflowBtn");
  if (button) { button.disabled = true; uiText(button, "Running..."); }
  try {
    const data = await workflowManagementFetch("/workflows/run", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ workflow: serverWorkflowSnapshot() }),
    });
    for (const result of data.results || []) {
      const node = runNodes.find(item => item.id === result.nodeId);
      if (!node) continue;
      node.connection = { status: result.status, message: result.message };
      node.testResult = { status: result.status, message: result.message, input: result.input, output: result.output };
    }
  } catch (error) {
    selected.connection = { status: "error", message: error.message || "Server workflow run failed. Check Schedule Status for execution history." };
  } finally {
    if (workflowId === activeWorkflowId) {
      renderIntegrationFields(selected);
      render();
    }
  }
}

function setStatus(id, value, ok = true, params = {}) {
  const el = document.getElementById(id);
  uiText(el, value, params);
  el.style.color = ok ? "#047857" : "#b91c1c";
}

async function refreshStatus() {
  try {
    const health = await loadJson("/health");
    setStatus("apiStatus", "{version} running", true, { version: health.version });
  } catch {
    setStatus("apiStatus", "offline", false);
  }

  try {
    const db = await loadJson("/db/status");
    setStatus("dbStatus", db.ok ? "{database}, {count} tables" : "not connected", db.ok, { database: db.database, count: db.tableCount });
    if (db.ok) {
      try {
        cellxSchema = await loadJson("/cellx-db/schema");
        if (selectedId) renderIntegrationFields(nodes.find((item) => item.id === selectedId));
      } catch {
        cellxSchema = { tables: [] };
      }
    }
  } catch {
    setStatus("dbStatus", "unknown", false);
  }
}

function addNode(type, x, y) {
  const defaults = typeDefaults[type] || typeDefaults.action;
  const node = {
    id: `node-${nextId++}`,
    type,
    name: defaults.name,
    action: defaults.action,
    notes: defaults.notes,
    icon: appIcons[defaults.name] || null,
    integrationSettings: {},
    connection: null,
    testResult: null,
    x,
    y,
  };
  nodes.push(node);
  render();
  selectNode(node.id);
}

function addCatalogNode(item, x, y) {
  const node = {
    id: `node-${nextId++}`,
    type: item.type,
    name: item.name,
    action: item.action,
    notes: item.desc,
    icon: appIcons[item.name] || null,
    integrationSettings: {},
    connection: null,
    testResult: null,
    x,
    y,
  };
  nodes.push(node);
  window.WorkflowVideo?.setupNode(node);
  render();
  selectNode(node.id);
  saveWorkflowDraft();
}

function nextCanvasSpot() {
  if (isNarrowScreen()) {
    return { x: 44, y: 36 + nodes.length * 112 };
  }
  return { x: 80 + (nodes.length % 3) * 240, y: 90 + Math.floor(nodes.length / 3) * 150 };
}

function renderNodeLibrary(filter = "") {
  const library = document.getElementById("nodeLibrary");
  const term = filter.trim().toLowerCase();
  library.innerHTML = "";

  for (const category of nodeCatalog) {
    const matches = category.children.filter((item) => {
      const haystack = `${category.group} ${item.sub} ${item.name} ${item.desc}`.toLowerCase();
      return !term || haystack.includes(term);
    });
    if (!matches.length) continue;

    const group = document.createElement("details");
    group.className = "node-group";
    group.open = Boolean(term) || ["Triggers", "Logic & Control", "CellX Database", "Shipping, Payment & Accounting", "AI Models"].includes(category.group);
    group.innerHTML = `<summary>${iconMarkup(categoryIcons[category.group], category.group, "group-icon")}<span>${uiLabel(category.group)}</span></summary>`;

    const bySub = matches.reduce((map, item) => {
      map[item.sub] = map[item.sub] || [];
      map[item.sub].push(item);
      return map;
    }, {});

    for (const [sub, items] of Object.entries(bySub)) {
      const subgroup = document.createElement("details");
      subgroup.className = "node-subgroup";
      subgroup.open = Boolean(term);
      subgroup.innerHTML = `<summary class="node-subgroup-title">${uiLabel(sub)}</summary>`;
      for (const item of items) {
        const nodeEl = document.createElement("div");
        nodeEl.className = `palette-node type-${item.type}`;
        nodeEl.draggable = true;
        nodeEl.dataset.type = item.type;
        nodeEl.dataset.name = item.name;
        nodeEl.dataset.action = item.action;
        nodeEl.dataset.notes = item.desc;
        nodeEl.innerHTML = `
          ${iconMarkup(appIcons[item.name], item.name)}
          <div class="palette-copy">
            <strong>${uiLabel(item.name)}</strong>
            ${uiLabel(item.desc)}
            <em class="node-tag">${item.type}</em>
          </div>
        `;
        nodeEl.addEventListener("dragstart", (event) => {
          event.dataTransfer.setData("node/catalog", JSON.stringify(item));
        });
        nodeEl.addEventListener("click", () => {
          if (!isNarrowScreen()) return;
          const spot = nextCanvasSpot();
          addCatalogNode(item, spot.x, spot.y);
          canvas.scrollIntoView({ behavior: "smooth", block: "start" });
        });
        subgroup.appendChild(nodeEl);
      }
      group.appendChild(subgroup);
    }

    library.appendChild(group);
  }
}

function render() {
  window.WorkflowVideo?.render();
  window.WorkflowPhotos?.render();
  updateCanvasExtent();
  if (workflowTitleEl) workflowTitleEl.textContent = workflowTitle || "Order Fulfillment Flow";
  if (workflowDescriptionEl) {
    workflowDescriptionEl.textContent = workflowDescription || "Drag nodes, reposition them, then connect steps.";
    workflowDescriptionEl.parentElement?.setAttribute("title", workflowDescriptionEl.textContent);
  }
  renderWorkflowResultArea();
  canvas.querySelectorAll(".workflow-node").forEach((el) => el.remove());
  for (const node of nodes) {
    const nodeIcon = node.icon || appIcons[node.name] || null;
    const el = document.createElement("div");
    el.className = `workflow-node type-${node.type}${node.id === selectedId ? " selected" : ""}`;
    el.style.left = `${node.x}px`;
    el.style.top = `${node.y}px`;
    el.dataset.id = node.id;
    el.innerHTML = `
      <div class="node-head">${iconMarkup(nodeIcon, node.name, "canvas-node-icon")}<span>${node.type.toUpperCase()}</span></div>
      <div class="node-body">
        <strong>${node.name}</strong>
        <span>${node.action}</span>
        ${node.connection ? `<em class="node-connection ${node.connection.status}">${uiLabel(node.connection.status === "success" ? "Connected" : node.connection.status === "manual" ? "Handoff Ready" : node.connection.status === "testing" ? "Testing" : "Error")}</em>` : ""}
      </div>
    `;
    canvas.appendChild(el);
  }
  drawLinks();
  const current = nodes.find((item) => item.id === selectedId);
  if (current && propIntegration) {
    const results = propIntegration.querySelector(".test-results");
    const nextMarkup = renderNodeTestResults();
    if (results) {
      results.outerHTML = nextMarkup;
      bindResultViewButtons();
    }
  }
  bindResultViewButtons();
}

function drawLinks() {
  linksSvg.innerHTML = `
    <defs>
      <marker id="arrow" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto" markerUnits="strokeWidth">
        <path d="M0,0 L0,6 L9,3 z" fill="#64748b"></path>
      </marker>
    </defs>
  `;
  for (const link of links) {
    const from = nodes.find((node) => node.id === link.from);
    const to = nodes.find((node) => node.id === link.to);
    if (!from || !to) continue;
    const x1 = from.x + 188;
    const y1 = from.y + 38;
    const x2 = to.x;
    const y2 = to.y + 38;
    const mid = Math.max(40, Math.abs(x2 - x1) / 2);
    const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
    path.setAttribute("d", `M ${x1} ${y1} C ${x1 + mid} ${y1}, ${x2 - mid} ${y2}, ${x2} ${y2}`);
    path.setAttribute("fill", "none");
    path.setAttribute("stroke", "#64748b");
    path.setAttribute("stroke-width", "2");
    path.setAttribute("marker-end", "url(#arrow)");
    linksSvg.appendChild(path);
  }
}

function selectNode(id) {
  selectedId = id;
  const node = nodes.find((item) => item.id === id);
  if (!node) return;

  if (connectMode) {
    if (!connectFrom) {
      connectFrom = id;
    } else if (connectFrom !== id && !links.some((link) => link.from === connectFrom && link.to === id)) {
      links.push({ from: connectFrom, to: id });
      connectFrom = null;
      connectMode = false;
      connectBtn.classList.remove("active");
    }
  }

  propName.value = node.name;
  propType.value = node.type;
  propAction.value = node.action;
  propNotes.value = node.notes;
  renderIntegrationFields(node);
  render();
}

function updateSelected() {
  const node = nodes.find((item) => item.id === selectedId);
  if (!node) return;
  node.name = propName.value;
  node.action = propAction.value;
  node.notes = propNotes.value;
  renderPropertyActionBar(node);
  render();
}

function clearProperties() {
  selectedId = null;
  propName.value = "";
  propType.value = "";
  propAction.value = "";
  propNotes.value = "";
  propIntegration.innerHTML = "";
  renderPropertyActionBar(null);
}

function removeNode(nodeId) {
  const node = nodes.find((item) => item.id === nodeId);
  if (!node) return;
  const shouldRemove = window.confirm(agentT("Remove \"{name}\" from this workflow?", { name: node.name }));
  if (!shouldRemove) return;

  nodes = nodes.filter((item) => item.id !== nodeId);
  links = links.filter((link) => link.from !== nodeId && link.to !== nodeId);
  if (connectFrom === nodeId) {
    connectFrom = null;
    connectMode = false;
    connectBtn.classList.remove("active");
  }

  if (selectedId === nodeId) {
    const nextNode = nodes[0];
    if (nextNode) {
      selectNode(nextNode.id);
    } else {
      clearProperties();
      render();
    }
    return;
  }

  render();
}

document.getElementById("nodeSearch").addEventListener("input", (event) => {
  renderNodeLibrary(event.target.value);
});

canvas.addEventListener("dragover", (event) => event.preventDefault());
canvas.addEventListener("drop", (event) => {
  event.preventDefault();
  const rect = canvas.getBoundingClientRect();
  const catalog = event.dataTransfer.getData("node/catalog");
  if (catalog) {
    addCatalogNode(JSON.parse(catalog), event.clientX - rect.left + canvas.scrollLeft - 94, event.clientY - rect.top + canvas.scrollTop - 20);
    return;
  }
  const type = event.dataTransfer.getData("node/type");
  if (!type) return;
  addNode(type, event.clientX - rect.left + canvas.scrollLeft - 94, event.clientY - rect.top + canvas.scrollTop - 20);
});

canvas.addEventListener("mousedown", (event) => {
  if (event.button !== 0) return;
  const nodeEl = event.target.closest(".workflow-node");
  if (!nodeEl) return;
  const node = nodes.find((item) => item.id === nodeEl.dataset.id);
  if (!node) return;
  selectNode(node.id);
  dragState = {
    id: node.id,
    startX: event.clientX,
    startY: event.clientY,
    nodeX: node.x,
    nodeY: node.y,
  };
});

canvas.addEventListener("contextmenu", (event) => {
  const nodeEl = event.target.closest(".workflow-node");
  if (!nodeEl) return;
  event.preventDefault();
  removeNode(nodeEl.dataset.id);
});

window.addEventListener("mousemove", (event) => {
  if (!dragState) return;
  const node = nodes.find((item) => item.id === dragState.id);
  const rect = canvas.getBoundingClientRect();
  if (!node) return;
  const limitWidth = Math.max(rect.width, canvas.scrollWidth);
  const limitHeight = Math.max(rect.height, canvas.scrollHeight);
  node.x = Math.max(12, Math.min(limitWidth - nodeWidth - 20, dragState.nodeX + event.clientX - dragState.startX));
  node.y = Math.max(12, Math.min(limitHeight - nodeHeight - 20, dragState.nodeY + event.clientY - dragState.startY));
  render();
});

window.addEventListener("mouseup", () => {
  dragState = null;
});

[propName, propAction, propNotes].forEach((input) => input.addEventListener("input", updateSelected));

connectBtn.addEventListener("click", () => {
  connectMode = !connectMode;
  connectFrom = null;
  connectBtn.classList.toggle("active", connectMode);
});

document.getElementById("autoLayoutBtn").addEventListener("click", () => {
  const positions = autoLayoutPositions();
  nodes.forEach((node, index) => {
    const [x, y] = positions[index % positions.length];
    node.x = x;
    node.y = y + Math.floor(index / positions.length) * (isNarrowScreen() ? 112 : 180);
  });
  fitNodesToCanvas();
  render();
});

document.getElementById("clearBtn").addEventListener("click", () => {
  nodes = [];
  links = [];
  selectedId = null;
  activeResultNodeId = null;
  connectFrom = null;
  workflowTitle = "Untitled Workflow";
  workflowDescription = "Drag nodes, reposition them, then connect steps.";
  syncActiveWorkflow();
  persistWorkflowStore();
  render();
});

document.getElementById("saveBtn").addEventListener("click", async () => {
  persistWorkflowStore();
  const button = document.getElementById("saveBtn");
  button.disabled = true;
  try {
    const message = await saveActiveSchedule();
    alert(agentT(message || "All workflow tabs saved in this browser."));
  } catch (error) {
    alert(agentT(uiMessage("Saved locally, but server schedule was not updated: {message}", { message: error.message })));
  } finally {
    button.disabled = false;
  }
});

document.getElementById("newWorkflowBtn").addEventListener("click", () => {
  syncActiveWorkflow();
  const name = window.prompt("Agent name", `New Agent ${workflows.length + 1}`) || `New Agent ${workflows.length + 1}`;
  const workflow = createBlankWorkflow(name.trim() || `New Agent ${workflows.length + 1}`);
  workflows.push(workflow);
  loadWorkflow(workflow.id);
  persistWorkflowStore();
});

workflowTabsEl?.addEventListener("click", (event) => {
  const closeTarget = event.target.closest("[data-close-workflow-id]");
  if (closeTarget) {
    event.stopPropagation();
    if (workflows.length <= 1) {
      alert(agentT("Keep at least one workflow tab open."));
      return;
    }
    const workflowId = closeTarget.dataset.closeWorkflowId;
    const workflow = workflows.find((item) => item.id === workflowId);
    if (!window.confirm(agentT("Close \"{name}\"? Save Draft first if you need to keep it.", { name: workflow?.name || agentT("this workflow") }))) return;
    const closingActive = workflowId === activeWorkflowId;
    workflows = workflows.filter((item) => item.id !== workflowId);
    if (closingActive) {
      loadWorkflow(workflows[0].id);
    } else {
      renderWorkflowTabs();
    }
    persistWorkflowStore();
    return;
  }
  const tab = event.target.closest("[data-workflow-id]");
  if (tab) {
    switchWorkflow(tab.dataset.workflowId);
  }
});

workflowTabsEl?.addEventListener("dblclick", (event) => {
  const tab = event.target.closest("[data-workflow-id]");
  if (!tab) return;
  const workflow = workflows.find((item) => item.id === tab.dataset.workflowId);
  if (!workflow) return;
  const nextName = window.prompt("Rename workflow", workflow.name || "Untitled Workflow");
  if (!nextName) return;
  workflow.name = nextName.trim() || workflow.name;
  if (workflow.id === activeWorkflowId) workflowTitle = workflow.name;
  persistWorkflowStore();
  render();
  renderWorkflowTabs();
});

document.getElementById("exportTemplateBtn").addEventListener("click", downloadWorkflowTemplate);

document.getElementById("browseTemplatesBtn")?.addEventListener("click", async () => {
  if (!templateBrowser) return;
  templateBrowser.hidden = !templateBrowser.hidden;
  if (!templateBrowser.hidden) {
    if (aiVoiceBuilderPanel) aiVoiceBuilderPanel.hidden = true;
    if (templateManagerPanel) templateManagerPanel.hidden = true;
    if (marketplacePanel) marketplacePanel.hidden = true;
    await loadTemplateLibrary();
    templateSearchEl?.focus();
  }
});

document.getElementById("closeTemplatesBtn")?.addEventListener("click", () => {
  if (templateBrowser) templateBrowser.hidden = true;
});

templateSearchEl?.addEventListener("input", renderTemplateLibrary);
templateCategoryFilterEl?.addEventListener("change", renderTemplateLibrary);

document.getElementById("aiVoiceBuilderBtn")?.addEventListener("click", () => {
  if (!aiVoiceBuilderPanel) return;
  aiVoiceBuilderPanel.hidden = !aiVoiceBuilderPanel.hidden;
  if (!aiVoiceBuilderPanel.hidden) {
    if (templateBrowser) templateBrowser.hidden = true;
    if (templateManagerPanel) templateManagerPanel.hidden = true;
    if (marketplacePanel) marketplacePanel.hidden = true;
    aiVoicePromptEl?.focus();
  }
});

document.getElementById("closeAiVoiceBuilderBtn")?.addEventListener("click", () => {
  stopVoiceWorkflowCapture();
  if (aiVoiceBuilderPanel) aiVoiceBuilderPanel.hidden = true;
});

document.getElementById("voiceListenBtn")?.addEventListener("click", startVoiceWorkflowCapture);
document.getElementById("voiceStopBtn")?.addEventListener("click", stopVoiceWorkflowCapture);
document.getElementById("voiceMuteBtn")?.addEventListener("click", () => {
  if (!realtimeVoice?.stream) return;
  const button = document.getElementById("voiceMuteBtn");
  const muted = button.getAttribute("aria-pressed") !== "true";
  realtimeVoice.stream.getAudioTracks().forEach((track) => { track.enabled = !muted; });
  button.setAttribute("aria-pressed", String(muted));
  uiText(button, muted ? "Unmute" : "Mute");
});
document.getElementById("voiceSendBtn")?.addEventListener("click", () => {
  if (window.VoiceScreenshots?.images().length) { window.VoiceScreenshots.send(); return; }
  const text = aiVoicePromptEl.value.trim();
  if (!text || !realtimeVoice) return;
  voiceLine("You", text);
  voiceSend(realtimeVoice, { type: "conversation.item.create", item: { type: "message", role: "user", content: [{ type: "input_text", text }] } });
  voiceSend(realtimeVoice, { type: "response.create" });
  aiVoicePromptEl.value = "";
});
window.addEventListener("pagehide", stopVoiceWorkflowCapture);
if (aiVoiceBuilderPanel) new MutationObserver(() => {
  if (aiVoiceBuilderPanel.hidden && realtimeVoice) stopVoiceWorkflowCapture();
}).observe(aiVoiceBuilderPanel, { attributes: true, attributeFilter: ["hidden"] });
document.getElementById("buildWorkflowWithAiBtn")?.addEventListener("click", buildWorkflowWithAi);
importAiDraftBtn?.addEventListener("click", importAiWorkflowDraft);

document.getElementById("manageTemplatesBtn")?.addEventListener("click", async () => {
  if (!templateManagerPanel) return;
  templateManagerPanel.hidden = !templateManagerPanel.hidden;
  if (!templateManagerPanel.hidden) {
    if (aiVoiceBuilderPanel) aiVoiceBuilderPanel.hidden = true;
    if (templateBrowser) templateBrowser.hidden = true;
    if (marketplacePanel) marketplacePanel.hidden = true;
    await loadTemplateManager();
  }
});

document.getElementById("closeTemplateManagerBtn")?.addEventListener("click", () => {
  if (templateManagerPanel) templateManagerPanel.hidden = true;
});

document.getElementById("refreshTemplateManagerBtn")?.addEventListener("click", loadTemplateManager);

templateManagerPanel?.addEventListener("click", async (event) => {
  const templateDelete = event.target.closest("[data-delete-managed-template]");
  const scriptDelete = event.target.closest("[data-delete-managed-script]");
  const timerAction = event.target.closest("[data-managed-timer-action]");
  try {
    if (templateDelete) {
      await deleteManagedTemplate(templateDelete.dataset.deleteManagedTemplate);
      return;
    }
    if (scriptDelete) {
      await deleteManagedScript(scriptDelete.dataset.deleteManagedScript);
      return;
    }
    if (timerAction) {
      await manageTimer(timerAction.dataset.managedTimer, timerAction.dataset.managedTimerAction);
    }
  } catch (error) {
    alert(agentT(error.message || "Management action failed."));
  }
});

document.getElementById("marketplaceBtn")?.addEventListener("click", async () => {
  if (!marketplacePanel) return;
  marketplacePanel.hidden = !marketplacePanel.hidden;
  if (!marketplacePanel.hidden) {
    if (aiVoiceBuilderPanel) aiVoiceBuilderPanel.hidden = true;
    if (templateBrowser) templateBrowser.hidden = true;
    if (templateManagerPanel) templateManagerPanel.hidden = true;
    await loadMarketplace(true);
    marketplaceSearchEl?.focus();
  }
});

document.getElementById("closeMarketplaceBtn")?.addEventListener("click", () => {
  if (marketplacePanel) marketplacePanel.hidden = true;
});

document.getElementById("refreshMarketplaceBtn")?.addEventListener("click", () => loadMarketplace(true));
document.getElementById("developerPublishForm")?.addEventListener("submit", publishMarketplaceTemplate);
document.getElementById("marketplaceAccountForm")?.addEventListener("submit", submitMarketplaceAuth);
document.getElementById("connectStripeBtn")?.addEventListener("click", connectStripePayout);
marketplaceSearchEl?.addEventListener("input", renderMarketplace);
marketplaceCategoryFilterEl?.addEventListener("change", renderMarketplace);

marketplaceListEl?.addEventListener("click", async (event) => {
  const deleteTarget = event.target.closest("[data-delete-marketplace-template]");
  if (deleteTarget) {
    const key = deleteTarget.dataset.deleteMarketplaceTemplate;
    const item = marketplaceItems.find((entry) => marketplaceItemKey(entry) === key);
    if (item) await deleteMarketplaceTemplate(item);
    return;
  }

  const reviewTarget = event.target.closest("[data-review-marketplace-template]");
  if (reviewTarget) {
    const item = marketplaceItems.find((entry) => entry.id === reviewTarget.dataset.reviewMarketplaceTemplate);
    if (item) await approveMarketplaceTemplate(item);
    return;
  }

  const importTarget = event.target.closest("[data-import-marketplace-template]");
  if (importTarget) {
    const item = marketplaceItems.find((entry) => entry.id === importTarget.dataset.importMarketplaceTemplate);
    if (item) await importMarketplaceTemplate(item);
    return;
  }
  const buyTarget = event.target.closest("[data-buy-marketplace-template]");
  if (buyTarget) {
    const item = marketplaceItems.find((entry) => entry.id === buyTarget.dataset.buyMarketplaceTemplate);
    if (item) await buyMarketplaceTemplate(item);
  }
});

document.addEventListener("click", (event) => {
  const copyButton = event.target.closest("[data-copy-node-output]");
  if (!copyButton) return;
  event.preventDefault();
  event.stopPropagation();
  copyNodeResultOutput(copyButton.dataset.copyNodeOutput, copyButton);
});

for (const [id, message] of Object.entries({
  aiVoiceStatus: "Ready.", aiVoiceDraftMeta: "No draft yet",
  apiStatus: "Checking...", dbStatus: "Checking...",
  templateLibraryStatus: "Loading templates...", templateManagerStatus: "Loading backend inventory...",
  marketplaceStatus: "Loading marketplace...",
})) uiText(document.getElementById(id), message);

renderMarketplaceAccount();

templateListEl?.addEventListener("click", async (event) => {
  const importTarget = event.target.closest("[data-import-library-template]");
  if (importTarget) {
    await importLibraryTemplate(templateLibrary.find((template) => template.file === importTarget.dataset.importLibraryTemplate));
    return;
  }
  const previewTarget = event.target.closest("[data-preview-template]");
  if (previewTarget) {
    await previewLibraryTemplate(templateLibrary.find((template) => template.file === previewTarget.dataset.previewTemplate));
  }
});

document.getElementById("importTemplateBtn").addEventListener("click", () => {
  document.getElementById("templateFileInput").click();
});

document.getElementById("templateFileInput").addEventListener("change", (event) => {
  importWorkflowTemplate(event.target.files[0]);
  event.target.value = "";
});

const savedMulti = localStorage.getItem(workflowStoreKey);
const savedLegacy = localStorage.getItem(legacyWorkflowStoreKey);
if (savedMulti) {
  try {
    const draft = JSON.parse(savedMulti);
    workflows = Array.isArray(draft.workflows) ? draft.workflows.map((item) => normalizeWorkflow(item, "Workflow", false)) : [];
    activeWorkflowId = draft.activeWorkflowId || workflows[0]?.id || null;
  } catch {
    workflows = [];
  }
} else if (savedLegacy) {
  try {
    const draft = JSON.parse(savedLegacy);
    workflows = [normalizeWorkflow({
      ...draft,
      name: draft.name || draft.workflowTitle || workflowTitle,
      description: draft.description || draft.workflowDescription || workflowDescription,
    }, "Workflow 1", false)];
    activeWorkflowId = workflows[0].id;
  } catch {
    workflows = [];
  }
}

if (!workflows.length) {
  activeWorkflowId = uniqueWorkflowId();
  const starter = seedStarterWorkflow();
  workflows = [starter];
}

loadWorkflow(activeWorkflowId || workflows[0]?.id);
refreshStatus();
renderNodeLibrary();

window.addEventListener("resize", () => {
  fitNodesToCanvas();
  render();
});
