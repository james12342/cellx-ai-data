const apiBase = "/ext-api";
const canvas = document.getElementById("canvas");
const linksSvg = document.getElementById("links");
const connectBtn = document.getElementById("connectModeBtn");
const propName = document.getElementById("propName");
const propType = document.getElementById("propType");
const propAction = document.getElementById("propAction");
const propNotes = document.getElementById("propNotes");
const propIntegration = document.getElementById("integrationFields");
const workflowTitleEl = document.getElementById("workflowTitle");
const workflowDescriptionEl = document.getElementById("workflowDescription");
const workflowTabsEl = document.getElementById("workflowTabs");
const templateBrowser = document.getElementById("templateBrowser");
const templateListEl = document.getElementById("templateList");
const templateSearchEl = document.getElementById("templateSearch");
const templateCategoryFilterEl = document.getElementById("templateCategoryFilter");
const templateLibraryStatusEl = document.getElementById("templateLibraryStatus");
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
let marketplaceItems = [];
let activeWorkflowId = null;
let selectedId = null;
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
const marketplaceStoreKey = "cellx-workflow-marketplace-draft";
const marketplaceUserStoreKey = "cellx-marketplace-user";
const marketplaceTokenStoreKey = "cellx-marketplace-token";
const sensitiveSettingPattern = /^(apiKey|secretKey|clientSecret|authHeader|authToken|bearerToken|password|token)$/i;
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

function safeWorkflowNodes(sourceNodes = [], stripSecrets = true) {
  return sourceNodes.map((node) => ({
    id: String(node.id || ""),
    type: String(node.type || "action"),
    name: String(node.name || "Workflow Step"),
    action: String(node.action || ""),
    notes: String(node.notes || ""),
    icon: node.icon ? String(node.icon) : null,
    x: Number.isFinite(Number(node.x)) ? Number(node.x) : 80,
    y: Number.isFinite(Number(node.y)) ? Number(node.y) : 80,
    integrationSettings: stripSecrets ? stripSensitiveSettings(node.integrationSettings || {}) : { ...(node.integrationSettings || {}) },
    connection: node.connection ? { ...node.connection } : null,
    testResult: node.testResult ? { ...node.testResult } : null,
  }));
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

function normalizeWorkflow(draft, fallbackName = "Untitled Workflow") {
  const valid = validateWorkflowTemplate({
    name: draft?.name || fallbackName,
    description: draft?.description || draft?.workflowDescription || "Drag nodes, reposition them, then connect steps.",
    nodes: Array.isArray(draft?.nodes) ? draft.nodes : [],
    links: Array.isArray(draft?.links) ? draft.links : [],
  });
  return {
    id: String(draft?.id || uniqueWorkflowId()),
    name: valid.name,
    description: valid.description,
    nodes: valid.nodes,
    links: valid.links,
  };
}

function loadWorkflow(workflowId) {
  const workflow = workflows.find((item) => item.id === workflowId) || workflows[0];
  if (!workflow) return;
  activeWorkflowId = workflow.id;
  workflowTitle = workflow.name || "Untitled Workflow";
  workflowDescription = workflow.description || "Drag nodes, reposition them, then connect steps.";
  nodes = safeWorkflowNodes(workflow.nodes || [], true);
  links = (workflow.links || []).map((link) => ({ from: String(link.from), to: String(link.to) }));
  selectedId = nodes[0]?.id || null;
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
      <span class="workflow-tab-close" data-close-workflow-id="${escapeHtml(workflow.id)}" title="Close workflow">×</span>
    </button>
  `).join("");
}

function nextIdFromNodes(items) {
  return items.reduce((max, node) => {
    const match = String(node.id || "").match(/^node-(\d+)$/);
    return Math.max(max, match ? Number(match[1]) + 1 : max);
  }, 1);
}

function validateWorkflowTemplate(template) {
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
    nodes: safeWorkflowNodes(template.nodes, true),
    links: validLinks.map((link) => ({ from: String(link.from), to: String(link.to) })),
  };
}

function applyWorkflowTemplate(template) {
  const draft = validateWorkflowTemplate(template);
  workflowTitle = draft.name;
  workflowDescription = draft.description;
  nodes = draft.nodes;
  links = draft.links;
  selectedId = nodes[0]?.id || null;
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
      alert("Workflow template imported as a new tab.");
    } catch (error) {
      alert(error.message || "Could not import this workflow template.");
    }
  });
  reader.addEventListener("error", () => {
    alert("Could not read this template file.");
  });
  reader.readAsText(file);
}

async function loadTemplateLibrary(force = false) {
  if (templateLibrary.length && !force) return templateLibrary;
  if (templateLibraryStatusEl) templateLibraryStatusEl.textContent = "Loading templates...";
  try {
    const response = await fetch(`${templateManifestPath}?v=${Date.now()}`, { cache: "no-store" });
    if (!response.ok) throw new Error(`Template manifest returned ${response.status}`);
    const manifest = await response.json();
    templateLibrary = Array.isArray(manifest.templates) ? manifest.templates : [];
    if (templateLibraryStatusEl) {
      templateLibraryStatusEl.textContent = `${templateLibrary.length} template${templateLibrary.length === 1 ? "" : "s"} available`;
    }
    renderTemplateCategoryFilter();
  } catch (error) {
    templateLibrary = [];
    if (templateLibraryStatusEl) templateLibraryStatusEl.textContent = "Template library unavailable";
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
    `<option value="">All categories</option>`,
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
    templateListEl.innerHTML = `<div class="template-empty">No templates found.</div>`;
    return;
  }
  templateListEl.innerHTML = filtered.map((template) => `
    <article class="template-card ${escapeHtml(templateCategoryClass(template.category))}">
      <div class="template-card-main">
        <div class="template-card-top">
          <span class="template-category">${escapeHtml(template.category || "Workflow")}</span>
          <span class="template-file">${escapeHtml(template.file || "")}</span>
        </div>
        <h2>${escapeHtml(template.name || "Workflow Template")}</h2>
        <p>${escapeHtml(template.description || "Generated workflow JSON template.")}</p>
        <div class="template-tags">
          ${(Array.isArray(template.tags) ? template.tags : []).map((tag) => `<span>${escapeHtml(tag)}</span>`).join("")}
        </div>
      </div>
      <div class="template-card-actions">
        <button type="button" data-preview-template="${escapeHtml(template.file || "")}">Preview JSON</button>
        <button class="primary" type="button" data-import-library-template="${escapeHtml(template.file || "")}">Import</button>
      </div>
    </article>
  `).join("");
}

async function fetchLibraryTemplate(template) {
  if (!template?.file) throw new Error("Template file is missing.");
  const response = await fetch(`./workflow-templates/${encodeURIComponent(template.file)}?v=${Date.now()}`, { cache: "no-store" });
  if (!response.ok) throw new Error(`Could not load ${template.file}.`);
  return response.json();
}

async function importLibraryTemplate(template) {
  try {
    const workflow = addWorkflowFromTemplate(await fetchLibraryTemplate(template), true);
    alert(`Imported "${workflow.name}" as a new workflow tab.`);
    if (templateBrowser) templateBrowser.hidden = true;
  } catch (error) {
    alert(error.message || "Could not import this template.");
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
    alert(error.message || "Could not preview this template.");
  }
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
    marketplaceAccountStatusEl.textContent = "Login or register before publishing and buying.";
    return;
  }
  const connectState = user.stripeConnectedAccountId ? "Stripe account linked" : "Stripe payout not linked";
  marketplaceAccountStatusEl.textContent = `${user.name || user.email} signed in as ${user.role || "user"}. ${connectState}.`;
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
    alert(`${mode === "register" ? "Registered" : "Logged in"}: ${data.user.email}`);
  } catch (error) {
    alert(error.message || "Marketplace account request failed.");
  }
}

async function connectStripePayout() {
  const user = marketplaceUser();
  const email = user?.email || document.getElementById("marketplaceAccountEmail")?.value || document.getElementById("marketplaceDeveloperEmail")?.value;
  if (!email) {
    alert("Enter or login with a developer email first.");
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
      alert(data.message || "Stripe Connect requires STRIPE_SECRET_KEY on the backend.");
    }
  } catch (error) {
    alert(error.message || "Could not start Stripe onboarding.");
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
    `<option value="">All categories</option>`,
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
  if (marketplaceStatusEl) marketplaceStatusEl.textContent = "Loading marketplace...";
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
  marketplaceItems = [...apiItems, ...localMarketplaceItems(), ...marketplaceSeedItems()];
  renderMarketplaceCategoryFilter();
  renderMarketplace();
  if (marketplaceStatusEl) {
    marketplaceStatusEl.textContent = `${marketplaceItems.length} marketplace template${marketplaceItems.length === 1 ? "" : "s"} available`;
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
    marketplaceListEl.innerHTML = `<div class="template-empty">No marketplace templates found.</div>`;
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
            <span class="template-file">${price ? `$${price.toFixed(2)}` : "Free"}</span>
          </div>
          <h2>${escapeHtml(item.name || "Marketplace Template")}</h2>
          <p>${escapeHtml(item.description || "Reusable workflow template.")}</p>
          <span class="marketplace-status-pill status-${escapeHtml(status)}">${escapeHtml(status.replaceAll("_", " "))}</span>
          <div class="marketplace-meta">
            <span>Developer: ${escapeHtml(item.developerName || "Developer")}</span>
            <span>Platform fee: $${escapeHtml(platformFee)}</span>
            <span>Developer share: $${escapeHtml(developerShare)}</span>
          </div>
        </div>
        <div class="template-card-actions">
          ${status === "pending_review" ? `<button type="button" data-review-marketplace-template="${escapeHtml(item.id)}">Approve</button>` : ""}
          <button type="button" data-buy-marketplace-template="${escapeHtml(item.id)}" ${canBuy ? "" : "disabled"}>${price ? "Checkout" : "Install"}</button>
          <button class="primary" type="button" data-import-marketplace-template="${escapeHtml(item.id)}">Import</button>
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
    alert(`Submitted "${data.item.name}" for review. Approve it before paid checkout.`);
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
    alert(`Published locally for demo. API note: ${error.message}`);
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
  alert(`Imported marketplace template "${workflow.name}" as a workflow tab.`);
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
        alert(`${data.message}\nPlatform commission: $${Number(data.platformFee || 0).toFixed(2)}\nDeveloper payout: $${Number(data.developerPayout || 0).toFixed(2)}`);
        return;
      }
      if (response.ok && data.ok) purchase = data.purchase;
    } catch (error) {
      console.warn("Marketplace checkout API unavailable.", error);
    }
  }
  const fee = Number(purchase?.platformFee ?? price * 0.25).toFixed(2);
  const payout = Number(purchase?.developerPayout ?? price * 0.75).toFixed(2);
  alert(`${price ? "Checkout ready" : "Free install ready"}.\nPlatform commission: $${fee}\nDeveloper payout: $${payout}`);
}

async function approveMarketplaceTemplate(item) {
  const adminToken = window.prompt("Enter marketplace admin review token");
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
    alert(`Approved "${data.item.name}". It is now available for checkout.`);
  } catch (error) {
    alert(error.message || "Could not approve template.");
  }
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
  if (["Slack", "Discord", "Telegram Bot", "WhatsApp Business", "Twilio SMS", "Mailchimp", "LinkedIn"].includes(node.name)) {
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
  if (node.type === "script") {
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
  if (node.type === "script") {
    if (!node.integrationSettings.scriptName) node.integrationSettings.scriptName = "amazon_bestsellers_demo.py";
    if (!node.integrationSettings.inputJson) node.integrationSettings.inputJson = '{"source_url":"https://www.amazon.com/Best-Sellers/zgbs","limit":20}';
    if (!node.integrationSettings.timeout) node.integrationSettings.timeout = "20";
    if (String(node.integrationSettings.scriptName || "").includes("orderdesk_orders_to_carriers.py") || /order desk/i.test(node.name || "")) {
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
  return /optional/i.test(placeholder) || ["baseUrl", "projectId", "accountId", "apiToken", "webhookSecret", "serviceAccountJson", "authHeader", "retryPolicy", "dataPolicy", "chatUrl", "manualResult", "args", "trueLabel", "falseLabel", "expressionPreview"].includes(key);
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
  return `<div class="connection-status ${status.status}"><strong>${label}</strong><span>${status.message || ""}</span></div>`;
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
  if (status === "success") return "Pass";
  if (status === "manual") return "Manual";
  if (status === "testing") return "Testing";
  if (status === "pending") return "Pending";
  return "Error";
}

function compactJson(value) {
  return JSON.stringify(value, null, 2);
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
    : '<option value="">Run previous node first</option>';
  const targetMarkup = targetOptions.length
    ? targetOptions.map(([value, text]) => `<option value="${escapeHtml(value)}">${escapeHtml(text)}</option>`).join("")
    : '<option value="">Choose a table first</option>';
  return `
    <div class="mapping-builder">
      <div class="mapping-title">
        <strong>Field Map Builder</strong>
        <span>Map previous result fields into the selected CellX table.</span>
      </div>
      <div class="mapping-row">
        <label>Source Field<select id="sourceFieldSelect">${sourceMarkup}</select></label>
        <label>CellX Field<select id="targetFieldSelect">${targetMarkup}</select></label>
      </div>
      <button id="addMappingBtn" type="button">Add Mapping</button>
    </div>
  `;
}

function renderManualHandoffTools(node) {
  if (node?.type !== "ai" || node.integrationSettings?.authMode !== "manual_web_handoff") return "";
  return `
    <div class="manual-handoff-tools">
      <button id="copyGptPromptBtn" class="primary" type="button">Copy GPT Prompt</button>
      <button id="openChatGptBtn" type="button">Open ChatGPT</button>
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
  } else if (node.type === "action") {
    base.update = { order_id: "CX-10042", status: "Ready to fulfill" };
  } else if (node.type === "script") {
    base.scriptName = node.integrationSettings?.scriptName || "amazon_bestsellers_demo.py";
    try {
      base.payload = JSON.parse(node.integrationSettings?.inputJson || "{}");
    } catch {
      base.payload = node.integrationSettings?.inputJson || "";
    }
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
  if (result?.output && node.type !== "condition" && node.type !== "carrier") return result.output;
  if (status === "error") {
    return result?.error || { ok: false, message };
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
  if ("orders_count" in output) rows.push(["Orders fetched", output.orders_count]);
  if ("row_count" in output) rows.push(["Rows", output.row_count]);
  if ("ups_count" in output) rows.push(["UPS", output.ups_count]);
  if ("fedex_count" in output) rows.push(["FedEx", output.fedex_count]);
  if ("manual_review_count" in output) rows.push(["Manual review", output.manual_review_count]);
  if ("shipment_payload_count" in output) rows.push(["Shipment payloads", output.shipment_payload_count]);
  if (Array.isArray(output.routes)) {
    output.routes.forEach((route) => rows.push([route.carrier, route.count]));
  }
  if (output.message) rows.push(["Message", output.message]);
  if (output.note) rows.push(["Note", output.note]);
  return rows;
}

function showNodeResultDialog(nodeId) {
  const node = nodes.find((item) => item.id === nodeId);
  if (!node) return;
  const result = node.testResult || {
    status: "pending",
    message: "Not tested yet.",
    input: buildNodeTestInput(node),
    output: { ok: null, message: "Click Test Selected or Run Workflow first." },
  };
  document.getElementById("resultDialog")?.remove();
  const summary = summarizeResultPayload(result.output || {});
  const dialog = document.createElement("div");
  dialog.id = "resultDialog";
  dialog.className = "result-dialog-backdrop";
  dialog.innerHTML = `
    <section class="result-dialog" role="dialog" aria-modal="true" aria-labelledby="resultDialogTitle">
      <header>
        <div>
          <strong id="resultDialogTitle">${escapeHtml(node.name)}</strong>
          <span>${escapeHtml(result.message || "Workflow node result")}</span>
        </div>
        <button type="button" data-close-result-dialog>Close</button>
      </header>
      ${summary.length ? `
        <div class="result-summary">
          ${summary.map(([label, value]) => `<div><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`).join("")}
        </div>
      ` : ""}
      <div class="result-dialog-grid">
        <div>
          <b>Input</b>
          <pre>${escapeHtml(compactJson(result.input || {}))}</pre>
        </div>
        <div>
          <b>Output</b>
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

function renderNodeTestResults() {
  if (!nodes.length) {
    return '<div class="test-results empty">No workflow nodes to test.</div>';
  }
  return `
    <section id="nodeTestResults" class="test-results">
      <div class="test-results-title">
        <strong>Node Test Results</strong>
        <span>Input and Output for each workflow node</span>
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
                <button type="button" data-view-node-result="${escapeHtml(node.id)}">View Result</button>
                <em>${testBadgeLabel(result.status)}</em>
              </span>
            </div>
            <p>${escapeHtml(result.message || "")}</p>
            <div class="io-grid">
              <div>
                <b>Input</b>
                <pre>${escapeHtml(compactJson(result.input || {}))}</pre>
              </div>
              <div>
                <b>Output</b>
                <pre>${escapeHtml(compactJson(result.output || {}))}</pre>
              </div>
            </div>
          </article>
        `;
      }).join("")}
    </section>
  `;
}

function renderIntegrationFields(node) {
  if (!propIntegration || !node) return;
  const spec = ensureIntegrationSettings(node);
  const fields = visibleIntegrationFields(spec, node);
  const requiredKeys = new Set(requiredIntegrationFields(spec, node));
  propIntegration.innerHTML = `
    <div class="integration-title">
      <strong>${spec.title}</strong>
      <span>${spec.summary}</span>
    </div>
    ${fields.map(({ key, label, type, placeholder, options }) => `
      <label class="integration-field">
        ${label}${requiredKeys.has(key) ? '<b class="required-mark">Required</b>' : '<b class="optional-mark">Optional</b>'}
        ${type === "select" ? `
          <select data-integration-key="${key}">
            ${(options || []).map(([value, text]) => `<option value="${value}"${node.integrationSettings[key] === value ? " selected" : ""}>${text}</option>`).join("")}
          </select>
        ` : type === "textarea" ? `
          <textarea data-integration-key="${key}" rows="4" placeholder="${placeholder}">${node.integrationSettings[key] || ""}</textarea>
        ` : `
          <input data-integration-key="${key}" type="${type}" value="${node.integrationSettings[key] || ""}" placeholder="${placeholder}">
        `}
      </label>
    `).join("")}
    ${renderCellXMappingBuilder(node)}
    ${renderManualHandoffTools(node)}
    <div class="connection-actions">
      <button id="testConnectionBtn" class="primary" type="button">Test Selected</button>
      <button id="runWorkflowBtn" type="button">Run Workflow</button>
      <button id="exportResultsBtn" type="button">Export Results</button>
      <button id="saveCredentialBtn" type="button">Save Config</button>
    </div>
    ${integrationStatusMarkup(node.connection)}
    ${renderNodeTestResults()}
    <p class="secret-note">Secrets should be stored on the backend or a secret manager. This designer keeps placeholders only.</p>
  `;
  propIntegration.querySelectorAll("[data-integration-key]").forEach((input) => {
    const updateSetting = () => {
      const current = nodes.find((item) => item.id === selectedId);
      if (!current) return;
    current.integrationSettings = current.integrationSettings || {};
    current.integrationSettings[input.dataset.integrationKey] = input.value;
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
  document.getElementById("testConnectionBtn").addEventListener("click", () => testSelectedIntegration());
  document.getElementById("runWorkflowBtn").addEventListener("click", () => testWorkflowIntegrations());
  document.getElementById("exportResultsBtn").addEventListener("click", () => exportWorkflowResults());
  bindResultViewButtons();
  document.getElementById("saveCredentialBtn").addEventListener("click", () => {
    const current = nodes.find((item) => item.id === selectedId);
    if (!current) return;
    current.connection = { status: "success", message: "Configuration saved as a local draft." };
    renderIntegrationFields(current);
    render();
  });
}

function bindResultViewButtons() {
  if (!propIntegration) return;
  propIntegration.querySelectorAll("[data-view-node-result]").forEach((button) => {
    if (button.dataset.boundViewResult === "true") return;
    button.dataset.boundViewResult = "true";
    button.addEventListener("click", () => showNodeResultDialog(button.dataset.viewNodeResult));
  });
}

async function loadJson(path) {
  const response = await fetch(`${apiBase}${path}`, { headers: { Accept: "application/json" } });
  if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
  return response.json();
}

async function postJson(path, payload) {
  const response = await fetch(`${apiBase}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
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
  if (!value || typeof value !== "object") return null;
  if (Array.isArray(value)) {
    return value.length ? value : null;
  }
  if (Array.isArray(value.rows) && value.rows.length) return value.rows;
  if (Array.isArray(value.items) && value.items.length) return value.items;
  for (const item of Object.values(value)) {
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
    current.connection = { status: "testing", message: `Exporting ${rows.length} rows to Excel...` };
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
    if (current) current.connection = { status: "success", message: `Exported ${rows.length} rows to ${fileName}.` };
  } catch (error) {
    if (current) current.connection = { status: "error", message: error.message || "Could not export results." };
  }
  if (current) {
    renderIntegrationFields(current);
    render();
  }
}

async function testNodeIntegration(node) {
  const spec = ensureIntegrationSettings(node);
  const required = requiredIntegrationFields(spec, node);
  const missing = required.filter((key) => !String(node.integrationSettings[key] || "").trim());
  const input = buildNodeTestInput(node);

  if (missing.length) {
    const message = `Missing required fields: ${missing.join(", ")}`;
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
    button.textContent = "Running...";
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
  const selected = nodes.find((item) => item.id === selectedId) || nodes[0];
  const button = document.getElementById("runWorkflowBtn");
  if (button) {
    button.disabled = true;
    button.textContent = "Running...";
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
    await testNodeIntegration(node);
  }

  renderIntegrationFields(selected);
  render();
  document.getElementById("nodeTestResults")?.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function setStatus(id, value, ok = true) {
  const el = document.getElementById(id);
  el.textContent = value;
  el.style.color = ok ? "#047857" : "#b91c1c";
}

async function refreshStatus() {
  try {
    const health = await loadJson("/health");
    setStatus("apiStatus", `${health.version} running`);
  } catch {
    setStatus("apiStatus", "offline", false);
  }

  try {
    const db = await loadJson("/db/status");
    setStatus("dbStatus", db.ok ? `${db.database}, ${db.tableCount} tables` : "not connected", db.ok);
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
  render();
  selectNode(node.id);
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
    group.innerHTML = `<summary>${iconMarkup(categoryIcons[category.group], category.group, "group-icon")}<span>${category.group}</span></summary>`;

    const bySub = matches.reduce((map, item) => {
      map[item.sub] = map[item.sub] || [];
      map[item.sub].push(item);
      return map;
    }, {});

    for (const [sub, items] of Object.entries(bySub)) {
      const subgroup = document.createElement("details");
      subgroup.className = "node-subgroup";
      subgroup.open = Boolean(term);
      subgroup.innerHTML = `<summary class="node-subgroup-title">${sub}</summary>`;
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
            <strong>${item.name}</strong>
            <span>${item.desc}</span>
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
  updateCanvasExtent();
  if (workflowTitleEl) workflowTitleEl.textContent = workflowTitle || "Order Fulfillment Flow";
  if (workflowDescriptionEl) workflowDescriptionEl.textContent = workflowDescription || "Drag nodes, reposition them, then connect steps.";
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
        ${node.connection ? `<em class="node-connection ${node.connection.status}">${node.connection.status === "success" ? "Connected" : node.connection.status === "manual" ? "Handoff Ready" : node.connection.status === "testing" ? "Testing" : "Error"}</em>` : ""}
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
  render();
}

function clearProperties() {
  selectedId = null;
  propName.value = "";
  propType.value = "";
  propAction.value = "";
  propNotes.value = "";
  propIntegration.innerHTML = "";
}

function removeNode(nodeId) {
  const node = nodes.find((item) => item.id === nodeId);
  if (!node) return;
  const shouldRemove = window.confirm(`Remove "${node.name}" from this workflow?`);
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
  connectFrom = null;
  workflowTitle = "Untitled Workflow";
  workflowDescription = "Drag nodes, reposition them, then connect steps.";
  syncActiveWorkflow();
  persistWorkflowStore();
  render();
});

document.getElementById("saveBtn").addEventListener("click", () => {
  persistWorkflowStore();
  alert("All workflow tabs saved in this browser.");
});

document.getElementById("newWorkflowBtn").addEventListener("click", () => {
  syncActiveWorkflow();
  const name = window.prompt("Workflow name", `New Workflow ${workflows.length + 1}`) || `New Workflow ${workflows.length + 1}`;
  const workflow = createBlankWorkflow(name.trim() || `New Workflow ${workflows.length + 1}`);
  workflows.push(workflow);
  loadWorkflow(workflow.id);
  persistWorkflowStore();
});

workflowTabsEl?.addEventListener("click", (event) => {
  const closeTarget = event.target.closest("[data-close-workflow-id]");
  if (closeTarget) {
    event.stopPropagation();
    if (workflows.length <= 1) {
      alert("Keep at least one workflow tab open.");
      return;
    }
    const workflowId = closeTarget.dataset.closeWorkflowId;
    const workflow = workflows.find((item) => item.id === workflowId);
    if (!window.confirm(`Close "${workflow?.name || "this workflow"}"? Save Draft first if you need to keep it.`)) return;
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
    await loadTemplateLibrary();
    templateSearchEl?.focus();
  }
});

document.getElementById("closeTemplatesBtn")?.addEventListener("click", () => {
  if (templateBrowser) templateBrowser.hidden = true;
});

templateSearchEl?.addEventListener("input", renderTemplateLibrary);
templateCategoryFilterEl?.addEventListener("change", renderTemplateLibrary);

document.getElementById("marketplaceBtn")?.addEventListener("click", async () => {
  if (!marketplacePanel) return;
  marketplacePanel.hidden = !marketplacePanel.hidden;
  if (!marketplacePanel.hidden) {
    if (templateBrowser) templateBrowser.hidden = true;
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
    workflows = Array.isArray(draft.workflows) ? draft.workflows.map((item) => normalizeWorkflow(item, "Workflow")) : [];
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
    }, "Workflow 1")];
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
