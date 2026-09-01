import fs from "node:fs/promises";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const sourceScript = "build_orderdesk_schema_workbook.mjs";
const outputDir = "outputs/order_desk_schema_20260830/split";
const source = await fs.readFile(sourceScript, "utf8");

function extractConst(name) {
  const start = source.indexOf(`const ${name} = `);
  if (start < 0) throw new Error(`Missing ${name}`);
  const after = source.indexOf("=", start) + 1;
  const end = source.indexOf("];", after) + 1;
  return Function(`return (${source.slice(after, end)});`)();
}

const data = {
  tables: extractConst("tables"),
  fields: extractConst("fields"),
  relationships: extractConst("relationships"),
  picklists: extractConst("picklists"),
  orderImportHeaders: extractConst("orderImportHeaders"),
  orderImportExample: extractConst("orderImportExample"),
  itemHeaders: extractConst("itemHeaders"),
  itemExample: extractConst("itemExample"),
  shipmentHeaders: extractConst("shipmentHeaders"),
  shipmentExample: extractConst("shipmentExample"),
};

const navy = "#0F172A";
const headerFill = "#DBEAFE";
const subFill = "#EFF6FF";
const border = "#CBD5E1";

function colName(index) {
  let n = index + 1;
  let s = "";
  while (n > 0) {
    const r = (n - 1) % 26;
    s = String.fromCharCode(65 + r) + s;
    n = Math.floor((n - 1) / 26);
  }
  return s;
}

function title(sheet, text, subtitle = "") {
  sheet.showGridLines = false;
  sheet.getRange("A1:H1").merge();
  sheet.getRange("A1").values = [[text]];
  sheet.getRange("A1").format = {
    fill: navy,
    font: { bold: true, color: "#FFFFFF", size: 16 },
  };
  sheet.getRange("A1").format.rowHeight = 30;
  if (subtitle) {
    sheet.getRange("A2:H2").merge();
    sheet.getRange("A2").values = [[subtitle]];
    sheet.getRange("A2").format = { fill: subFill, font: { color: "#334155" }, wrapText: true };
    sheet.getRange("A2").format.rowHeight = 38;
  }
}

function writeTable(sheet, startCell, headers, rows, tableName) {
  const startColText = startCell.match(/[A-Z]+/)[0];
  const startCol = startColText.split("").reduce((sum, ch) => sum * 26 + ch.charCodeAt(0) - 64, 0) - 1;
  const startRow = Number(startCell.match(/\d+/)[0]);
  const dataRows = [headers, ...rows];
  const endCol = colName(startCol + headers.length - 1);
  const endRow = startRow + dataRows.length - 1;
  const address = `${startCell}:${endCol}${endRow}`;
  const range = sheet.getRange(address);
  range.values = dataRows;
  sheet.getRange(`${startCell}:${endCol}${startRow}`).format = {
    fill: headerFill,
    font: { bold: true, color: navy },
    borders: { preset: "doubleBottom", style: "thin", color: border },
  };
  range.format.borders = { preset: "outside", style: "thin", color: border };
  range.format.wrapText = true;
  const table = sheet.tables.add(address, true, tableName);
  table.style = "TableStyleMedium2";
  table.showFilterButton = true;
  return range;
}

function finishSheet(sheet) {
  const used = sheet.getUsedRange();
  used.format.font.name = "Aptos";
  used.format.font.size = 10;
  used.format.verticalAlignment = "top";
  used.format.autofitRows();
}

async function saveWorkbook(fileName, build) {
  const workbook = Workbook.create();
  await build(workbook);
  for (const sheet of workbook.worksheets.items) finishSheet(sheet);

  const first = workbook.worksheets.getItemAt(0);
  const preview = await workbook.render({ sheetName: first.name, autoCrop: "all", scale: 1, format: "png" });
  await fs.writeFile(`${outputDir}/${fileName.replace(".xlsx", ".png")}`, new Uint8Array(await preview.arrayBuffer()));

  const errors = await workbook.inspect({
    kind: "match",
    searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
    options: { useRegex: true, maxResults: 50 },
    summary: `${fileName} formula error scan`,
  });
  console.log(`${fileName}: ${errors.ndjson}`);

  const output = await SpreadsheetFile.exportXlsx(workbook);
  await output.save(`${outputDir}/${fileName}`);
}

await fs.mkdir(outputDir, { recursive: true });

await saveWorkbook("01_field_dictionary.xlsx", async (workbook) => {
  const sheet = workbook.worksheets.add("Field Dictionary");
  title(sheet, "Order Desk OMS Field Dictionary", "Column-level database design for CellX/RDP table generation.");
  writeTable(sheet, "A4", ["Table", "Field", "Display Name", "DB Type", "Length", "Required", "Key", "Default", "Example", "Notes"], data.fields, "FieldDictionaryTable");
  sheet.getRange("A:J").format.columnWidth = 18;
  sheet.getRange("C:C").format.columnWidth = 24;
  sheet.getRange("J:J").format.columnWidth = 42;
  sheet.getRange("F5:F300").dataValidation = { rule: { type: "list", values: ["YES", "NO"] } };
  sheet.freezePanes.freezeRows(4);
  sheet.freezePanes.freezeColumns(2);
});

await saveWorkbook("02_tables_and_relationships.xlsx", async (workbook) => {
  const sheet = workbook.worksheets.add("ERD");
  title(sheet, "Order Desk OMS Tables and Relationships", "Use this before creating menus, main forms, child tables, and permissions.");
  writeTable(sheet, "A4", ["Table", "Module", "Purpose", "Primary Key"], data.tables, "TablesTable");
  writeTable(sheet, "F4", ["From", "To", "Cardinality", "Notes"], data.relationships, "RelationshipsTable");
  sheet.getRange("A:D").format.columnWidth = 28;
  sheet.getRange("F:I").format.columnWidth = 30;
  sheet.freezePanes.freezeRows(4);
});

await saveWorkbook("03_import_template_orders.xlsx", async (workbook) => {
  const sheet = workbook.worksheets.add("Import Orders");
  title(sheet, "Excel Import Template - Orders", "Use this for order header imports. Keep order_date as yyyy-mm-dd hh:mm:ss.");
  writeTable(sheet, "A4", data.orderImportHeaders, [data.orderImportExample], "ImportOrdersTable");
  sheet.getRange("AC5:AC5").setNumberFormat("yyyy-mm-dd hh:mm:ss");
  sheet.getRange("A:AF").format.columnWidth = 20;
  sheet.freezePanes.freezeRows(4);
});

await saveWorkbook("04_import_template_order_items.xlsx", async (workbook) => {
  const sheet = workbook.worksheets.add("Import Order Items");
  title(sheet, "Excel Import Template - Order Items", "Use external_order_id to connect line items to imported orders.");
  writeTable(sheet, "A4", data.itemHeaders, [data.itemExample], "ImportItemsTable");
  sheet.getRange("A:L").format.columnWidth = 22;
  sheet.freezePanes.freezeRows(4);
});

await saveWorkbook("05_import_template_shipments.xlsx", async (workbook) => {
  const sheet = workbook.worksheets.add("Import Shipments");
  title(sheet, "Excel Import Template - Shipments", "Use this after orders are imported or synced.");
  writeTable(sheet, "A4", data.shipmentHeaders, [data.shipmentExample], "ImportShipmentsTable");
  sheet.getRange("L5:L5").setNumberFormat("yyyy-mm-dd");
  sheet.getRange("A:L").format.columnWidth = 22;
  sheet.freezePanes.freezeRows(4);
});

await saveWorkbook("06_picklists.xlsx", async (workbook) => {
  const sheet = workbook.worksheets.add("Picklists");
  title(sheet, "Picklists and Validation Values", "Use these values for dropdowns, enums, and import validation.");
  writeTable(sheet, "A4", ["Field", "Allowed Values"], data.picklists, "PicklistsTable");
  sheet.getRange("A:A").format.columnWidth = 28;
  sheet.getRange("B:B").format.columnWidth = 90;
});

await saveWorkbook("07_implementation_notes.xlsx", async (workbook) => {
  const sheet = workbook.worksheets.add("Implementation Notes");
  title(sheet, "Order Desk OMS Implementation Notes", "Practical notes for building this in CellX/RDP and avoiding import failures.");
  sheet.getRange("A4:C14").values = [
    ["Area", "Recommendation", "Reason"],
    ["Order date", "Store as datetime and import as yyyy-mm-dd hh:mm:ss.", "Prevents MySQL Incorrect datetime errors from Excel serial values."],
    ["Money", "Use decimal(12,2), never float/double.", "Avoids rounding issues in order totals and refunds."],
    ["Identifiers", "Keep external ids, postal codes, tracking numbers, SKUs as varchar.", "Leading zeros and letters must be preserved."],
    ["Address", "Use a child table with address_type.", "Supports shipping, billing/customer, and return addresses without many duplicate columns."],
    ["Metadata", "Use JSON columns for flexible channel-specific fields.", "Keeps core schema stable while integrations differ."],
    ["Payments", "Do not store full card numbers.", "Store masked number and gateway transaction id only."],
    ["Search", "Index external_order_id, email, status, payment_status, order_date, tracking_number.", "Matches common Order Desk list filters."],
    ["Security", "Limit export/import and integration settings to admin roles.", "These areas expose sensitive customer and payment-adjacent data."],
    ["Automation", "Keep rules in JSON but log each execution to order_history.", "Makes workflow behavior auditable."],
    ["Source", "https://apidocs.orderdesk.com/", "Order Desk public API reference used for field inspiration."],
  ];
  sheet.getRange("A4:C4").format = { fill: headerFill, font: { bold: true, color: navy } };
  sheet.getRange("A4:C14").format.borders = { preset: "all", style: "thin", color: border };
  sheet.getRange("A:A").format.columnWidth = 24;
  sheet.getRange("B:B").format.columnWidth = 70;
  sheet.getRange("C:C").format.columnWidth = 62;
  sheet.getRange("A4:C14").format.wrapText = true;
});

console.log(`Saved split workbooks to ${outputDir}`);
