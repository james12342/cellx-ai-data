import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const OUT_DIR = "outputs/amazon_bestsellers_example";
const JSON_PATH = path.join(OUT_DIR, "amazon_best_sellers_sample.json");
const XLSX_PATH = path.join(OUT_DIR, "amazon_best_sellers_workflow_example.xlsx");

async function writeBlob(filePath, blob) {
  await fs.writeFile(filePath, new Uint8Array(await blob.arrayBuffer()));
}

function matrixFromObjects(rows, headers) {
  return [
    headers,
    ...rows.map((row) => headers.map((header) => row[header] ?? "")),
  ];
}

function parseMoney(value) {
  const number = Number(String(value || "").replace(/[$,]/g, ""));
  return Number.isFinite(number) ? number : null;
}

function parseNumber(value) {
  const number = Number(String(value || "").replace(/,/g, ""));
  return Number.isFinite(number) ? number : null;
}

function styleTable(sheet, rangeAddress, headerAddress) {
  sheet.getRange(rangeAddress).format = {
    borders: { preset: "inside", style: "thin", color: "#D8E2F0" },
    font: { color: "#202938" },
    wrapText: true,
  };
  sheet.getRange(headerAddress).format = {
    fill: "#1F3478",
    font: { bold: true, color: "#FFFFFF" },
  };
}

function setColumnWidths(sheet, widths) {
  widths.forEach((width, index) => {
    sheet.getRangeByIndexes(0, index, 1, 1).format.columnWidthPx = width;
  });
}

async function main() {
  const source = JSON.parse(await fs.readFile(JSON_PATH, "utf8"));
  const scrapedAtText = `${source.scraped_at.replace("T", " ").slice(0, 19)} UTC`;
  const rows = source.output.map((row) => ({
    ...row,
    price: parseMoney(row.price),
    rating: parseNumber(row.rating),
    reviews: parseNumber(row.reviews),
    scraped_at: scrapedAtText,
  }));
  const workbook = Workbook.create();

  const demo = workbook.worksheets.add("Workflow Demo");
  const raw = workbook.worksheets.add("Raw Data");
  const transformed = workbook.worksheets.add("JSON Transform Output");

  demo.showGridLines = false;
  raw.showGridLines = false;
  transformed.showGridLines = false;

  demo.getRange("A1:F1").merge();
  demo.getRange("A1").values = [["Amazon Best Sellers Workflow Example"]];
  demo.getRange("A1").format = { fill: "#EAF4FF", font: { bold: true, color: "#14213D", size: 18 } };
  demo.getRange("A3:B9").values = [
    ["Source page", source.source_url],
    ["Scraped at", scrapedAtText],
    ["Workflow node", source.workflow_node],
    ["Rows captured", rows.length],
    ["Fields captured", "rank, category, asin, sku, title, brand, price, rating, reviews, estimated demand, URL, notes"],
    ["Important caveat", "Seller SKU is not public on Amazon pages; the demo uses ASIN as SKU. True seller SKU needs Amazon SP-API or seller account data."],
    ["Demo use", "Use this file as the Output of the Amazon Bestseller Search + JSON Transform nodes."],
  ];
  demo.getRange("A3:A9").format = { fill: "#F3F8FF", font: { bold: true, color: "#1F3478" } };
  demo.getRange("A3:B9").format = {
    borders: { preset: "inside", style: "thin", color: "#D8E2F0" },
    wrapText: true,
  };
  demo.getRange("A11:F11").values = [["Step", "Node", "Input", "Output", "Status", "Notes"]];
  demo.getRange("A12:F17").values = [
    [1, "Schedule", "manual or daily trigger", "best-sellers scrape requested", "Ready", "Starts the workflow."],
    [2, "Amazon Bestseller Search", "Amazon Best Sellers public page", `${rows.length} product cards captured`, "Ready", "Public page only, no login bypass."],
    [3, "JSON Transform", "raw product cards", "normalized product rows", "Ready", "Matches the output schema."],
    [4, "Excel Export", "normalized rows", "CSV + XLSX files", "Ready", "This workbook is the example output."],
    [5, "OpenAI GPT-5", "Excel file", "supplier opportunity analysis", "Manual", "Upload this workbook into ChatGPT for sourcing analysis."],
    [6, "Email Supplier Report", "approved analysis", "email report draft", "Next", "Can connect to Outlook/Gmail later."],
  ];
  styleTable(demo, "A11:F17", "A11:F11");
  setColumnWidths(demo, [56, 170, 210, 230, 90, 320]);

  const rawHeaders = ["rank", "category", "title", "price", "rating", "reviews", "product_url", "scraped_at"];
  raw.getRangeByIndexes(0, 0, rows.length + 1, rawHeaders.length).values = matrixFromObjects(rows, rawHeaders);
  styleTable(raw, `A1:H${rows.length + 1}`, "A1:H1");
  setColumnWidths(raw, [58, 170, 430, 86, 70, 92, 520, 180]);
  raw.getRange(`D2:D${rows.length + 1}`).format.numberFormat = "$#,##0.00";
  raw.getRange(`E2:E${rows.length + 1}`).format.numberFormat = "0.0";
  raw.getRange(`F2:F${rows.length + 1}`).format.numberFormat = "#,##0";
  raw.freezePanes.freezeRows(1);

  const transformHeaders = ["rank", "category", "asin", "sku", "title", "brand", "price", "rating", "reviews", "estimated_demand", "product_url", "notes"];
  transformed.getRangeByIndexes(0, 0, rows.length + 1, transformHeaders.length).values = matrixFromObjects(rows, transformHeaders);
  styleTable(transformed, `A1:L${rows.length + 1}`, "A1:L1");
  setColumnWidths(transformed, [58, 165, 110, 110, 420, 150, 86, 70, 92, 130, 500, 360]);
  transformed.getRange(`G2:G${rows.length + 1}`).format.numberFormat = "$#,##0.00";
  transformed.getRange(`H2:H${rows.length + 1}`).format.numberFormat = "0.0";
  transformed.getRange(`I2:I${rows.length + 1}`).format.numberFormat = "#,##0";
  transformed.freezePanes.freezeRows(1);

  const preview = await workbook.render({ sheetName: "Workflow Demo", autoCrop: "all", scale: 1, format: "png" });
  await writeBlob(path.join(OUT_DIR, "workflow_demo_preview.png"), preview);

  const inspect = await workbook.inspect({
    kind: "workbook,sheet,table",
    maxChars: 5000,
    tableMaxRows: 8,
    tableMaxCols: 8,
  });
  await fs.writeFile(path.join(OUT_DIR, "workbook_inspect.ndjson"), inspect.ndjson, "utf8");

  const output = await SpreadsheetFile.exportXlsx(workbook);
  await output.save(XLSX_PATH);
  console.log(path.resolve(XLSX_PATH));
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
