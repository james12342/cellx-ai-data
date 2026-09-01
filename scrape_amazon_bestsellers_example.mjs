import fs from "node:fs/promises";
import path from "node:path";
import { chromium } from "playwright";

const OUT_DIR = "outputs/amazon_bestsellers_example";
const AMAZON_URL = "https://www.amazon.com/Best-Sellers/zgbs";
const CHROME_PATH = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";

function csvEscape(value) {
  const text = String(value ?? "");
  return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

function estimateDemand(rank, reviewCount) {
  const reviews = Number(String(reviewCount || "").replace(/,/g, "")) || 0;
  if (rank <= 3 && reviews >= 100000) return "Very high";
  if (rank <= 10 && reviews >= 10000) return "High";
  if (rank <= 20 || reviews >= 5000) return "Medium";
  return "Needs validation";
}

function guessBrand(title) {
  const cleaned = String(title || "").trim();
  const explicit = cleaned.match(/\b(Owala|HydroJug|Etekcity|Stanley|CAROTE|KitchenAid|Keurig|Ninja|COSORI|Amazon Basics)\b/i);
  if (explicit) return explicit[1];
  return cleaned.split(/\s+/).slice(0, 2).join(" ");
}

function toCsv(rows) {
  const headers = [
    "rank",
    "category",
    "asin",
    "sku",
    "title",
    "brand",
    "price",
    "rating",
    "reviews",
    "estimated_demand",
    "product_url",
    "notes",
    "scraped_at",
  ];
  return [
    headers.join(","),
    ...rows.map((row) => headers.map((header) => csvEscape(row[header])).join(",")),
  ].join("\n");
}

async function main() {
  await fs.mkdir(OUT_DIR, { recursive: true });

  const browser = await chromium.launch({
    headless: true,
    executablePath: CHROME_PATH,
  });
  const page = await browser.newPage({
    viewport: { width: 1800, height: 1400 },
    userAgent: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36",
  });

  await page.goto(AMAZON_URL, { waitUntil: "domcontentloaded", timeout: 30000 });
  await page.waitForTimeout(5000);
  await page.screenshot({ path: path.join(OUT_DIR, "amazon_best_sellers_page.png"), fullPage: false });

  const scrapedAt = new Date().toISOString();
  const rawRows = await page.evaluate(() => {
    function text(el) {
      return (el?.innerText || el?.textContent || "").replace(/\s+/g, " ").trim();
    }

    function titleFromCard(body) {
      return body
        .replace(/^#\d+\s*/, "")
        .replace(/\s*\d(?:\.\d)? out of 5 stars.*$/, "")
        .trim();
    }

    function categoryFromHref(href) {
      const slug = (href.match(/zg_bs_c_([a-z0-9-]+)_d_sccl/i) || [])[1];
      const map = {
        electronics: "Electronics",
        beauty: "Beauty & Personal Care",
        hpc: "Health & Household",
        kitchen: "Kitchen & Dining",
        automotive: "Automotive",
        books: "Books",
        fashion: "Clothing, Shoes & Jewelry",
      };
      if (!slug) return "";
      return map[slug] || slug.replace(/-/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
    }

    function categoryFor(card) {
      let node = card;
      for (let i = 0; i < 8 && node; i += 1) {
        const heading = node.querySelector?.("h2, h1, [role='heading']");
        const headingText = text(heading);
        if (/Best Sellers in/i.test(headingText)) return headingText.replace(/^Best Sellers in\s*/i, "");
        node = node.parentElement;
      }
      let prev = card;
      for (let i = 0; i < 40 && prev; i += 1) {
        prev = prev.previousElementSibling || prev.parentElement?.previousElementSibling;
        const headingText = text(prev?.querySelector?.("h2, h1, [role='heading']") || prev);
        if (/Best Sellers in/i.test(headingText)) return headingText.replace(/^Best Sellers in\s*/i, "");
      }
      return "Amazon Best Sellers";
    }

    const cards = [...document.querySelectorAll("[data-asin], #gridItemRoot, .p13n-sc-uncoverable-faceout")];
    return cards.map((card) => {
      const body = text(card);
      const rankText = text(card.querySelector(".zg-bdg-text")) || (body.match(/#\d+/) || [""])[0];
      const rank = Number(rankText.replace(/[^\d]/g, "")) || null;
      const productLink = [...card.querySelectorAll("a[href*='/dp/'], a[href*='/gp/product/']")]
        .find((link) => text(link).length > 20 || link.querySelector("img"));
      const href = productLink?.href || "";
      const asin = card.getAttribute("data-asin") || (href.match(/\/(?:dp|gp\/product)\/([A-Z0-9]{10})/) || [])[1] || "";
      const image = card.querySelector("img");
      const titleCandidates = [
        ...card.querySelectorAll("._cDEzb_p13n-sc-css-line-clamp-3_g3dy1, ._cDEzb_p13n-sc-css-line-clamp-2_EWgCb, a span"),
      ]
        .map(text)
        .filter((item) => item.length > 20 && !/^\d+(?:,\d+)*$/.test(item));
      const title = titleCandidates[0] || image?.alt || titleFromCard(body);
      const price = (body.match(/\$\d+(?:\.\d{2})?/) || [""])[0];
      const rating = (body.match(/\d(?:\.\d)? out of 5 stars/) || [""])[0].replace(" out of 5 stars", "");
      const reviews = (body.match(/(?:\d{1,3},)*\d{3,}/) || [""])[0];

      return {
        rank,
        category: categoryFromHref(href) || categoryFor(card),
        asin,
        title,
        price,
        rating,
        reviews,
        product_url: href ? href.split("?")[0] : "",
      };
    }).filter((row) => row.rank && row.title);
  });

  const deduped = [];
  const seen = new Set();
  for (const row of rawRows) {
    const key = row.asin || `${row.category}|${row.rank}|${row.title}`;
    if (seen.has(key)) continue;
    seen.add(key);
    deduped.push(row);
  }

  const rows = deduped.slice(0, 20).map((row) => ({
    rank: row.rank,
    category: row.category,
    asin: row.asin,
    sku: row.asin || "Public page does not expose seller SKU",
    title: row.title,
    brand: guessBrand(row.title),
    price: row.price,
    rating: row.rating,
    reviews: row.reviews,
    estimated_demand: estimateDemand(row.rank, row.reviews),
    product_url: row.product_url,
    notes: row.asin ? "Captured from public Amazon Best Sellers page; seller SKU requires SP-API or seller account data." : "Public listing captured; ASIN not exposed in parsed link.",
    scraped_at: scrapedAt,
  }));

  const workflowExample = {
    source_url: AMAZON_URL,
    scraped_at: scrapedAt,
    workflow_node: "JSON Transform",
    input: {
      page: "Amazon Best Sellers",
      raw_product_cards: rows.length,
      fields_seen_on_page: ["rank", "title", "price", "rating", "reviews", "product_url"],
    },
    output_schema: ["rank", "category", "asin", "sku", "title", "brand", "price", "rating", "reviews", "estimated_demand", "product_url", "notes"],
    output: rows,
  };

  await fs.writeFile(path.join(OUT_DIR, "amazon_best_sellers_sample.json"), JSON.stringify(workflowExample, null, 2), "utf8");
  await fs.writeFile(path.join(OUT_DIR, "amazon_best_sellers_sample.csv"), toCsv(rows), "utf8");

  await browser.close();
  console.log(JSON.stringify({ count: rows.length, outDir: path.resolve(OUT_DIR), sample: rows.slice(0, 5) }, null, 2));
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
