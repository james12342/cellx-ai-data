#!/usr/bin/env python3
import json
import re
import sys
from datetime import datetime, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen


DEFAULT_SOURCE_URL = "https://finance.yahoo.com/markets/stocks/most-active/"
SCREENER_URL = "https://query1.finance.yahoo.com/v1/finance/screener/predefined/saved"


def read_payload():
    raw = sys.stdin.read().strip() or "{}"
    try:
        return json.loads(raw)
    except Exception:
        return {}


def number(value):
    if value is None:
        return None
    try:
        return float(value)
    except Exception:
        return None


def integer(value):
    if value is None:
        return None
    try:
        return int(value)
    except Exception:
        return None


def format_market_cap(value):
    value = number(value)
    if value is None:
        return ""
    if value >= 1_000_000_000_000:
        return f"{value / 1_000_000_000_000:.2f}T"
    if value >= 1_000_000_000:
        return f"{value / 1_000_000_000:.2f}B"
    if value >= 1_000_000:
        return f"{value / 1_000_000:.2f}M"
    return f"{value:.0f}"


def fetch_json(url):
    request = Request(
        url,
        headers={
            "User-Agent": "CellAIDataWorkflowDemo/1.0 (+https://app.cellaidata.com)",
            "Accept": "application/json,text/plain,*/*",
            "Accept-Language": "en-US,en;q=0.9",
            "Origin": "https://finance.yahoo.com",
            "Referer": DEFAULT_SOURCE_URL,
        },
    )
    with urlopen(request, timeout=20) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return json.loads(response.read().decode(charset, errors="replace"))


def fetch_html_fallback(url):
    request = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/152 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
    with urlopen(request, timeout=20) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read(1500000).decode(charset, errors="replace")


def quote_page(symbol):
    return f"https://finance.yahoo.com/quote/{symbol}/"


def quote_to_row(quote, rank):
    symbol = quote.get("symbol") or quote.get("ticker") or ""
    price = number(quote.get("regularMarketPrice") or quote.get("intradayprice"))
    change = number(quote.get("regularMarketChange") or quote.get("intradaypricechange"))
    change_percent = number(quote.get("regularMarketChangePercent") or quote.get("percentchange"))
    volume = integer(quote.get("regularMarketVolume") or quote.get("dayvolume"))
    avg_volume = integer(quote.get("averageDailyVolume3Month") or quote.get("avgdailyvol3m"))
    market_cap = integer(quote.get("marketCap") or quote.get("intradaymarketcap"))
    return {
        "rank": rank,
        "symbol": symbol,
        "name": quote.get("longName") or quote.get("shortName") or quote.get("displayName") or quote.get("companyshortname") or "",
        "display_name": quote.get("displayName") or "",
        "exchange": quote.get("fullExchangeName") or quote.get("exchange") or "",
        "quote_type": quote.get("quoteType") or "",
        "currency": quote.get("currency") or "",
        "price": price,
        "change": change,
        "change_percent": change_percent,
        "volume": volume,
        "average_volume_3m": avg_volume,
        "relative_volume_3m": round(volume / avg_volume, 2) if volume and avg_volume else None,
        "market_cap": market_cap,
        "market_cap_display": format_market_cap(market_cap),
        "day_low": number(quote.get("regularMarketDayLow")),
        "day_high": number(quote.get("regularMarketDayHigh")),
        "day_range": quote.get("regularMarketDayRange") or "",
        "previous_close": number(quote.get("regularMarketPreviousClose")),
        "open": number(quote.get("regularMarketOpen")),
        "fifty_two_week_low": number(quote.get("fiftyTwoWeekLow")),
        "fifty_two_week_high": number(quote.get("fiftyTwoWeekHigh")),
        "trailing_pe": number(quote.get("trailingPE")),
        "forward_pe": number(quote.get("forwardPE")),
        "eps_ttm": number(quote.get("epsTrailingTwelveMonths")),
        "analyst_rating": quote.get("averageAnalystRating") or "",
        "market_state": quote.get("marketState") or "",
        "quote_source": quote.get("quoteSourceName") or "",
        "sector": quote.get("sector") or "",
        "industry": quote.get("industry") or "",
        "yahoo_url": quote_page(symbol) if symbol else "",
    }


def scrape_symbols_from_html(page_html, limit):
    symbols = []
    for match in re.finditer(r'/quote/([A-Z][A-Z0-9.\-]{0,12})(?:[/?"]|%3F)', page_html):
        symbol = match.group(1)
        if symbol not in symbols:
            symbols.append(symbol)
        if len(symbols) >= limit:
            break
    return symbols


def fetch_most_active(count, offset):
    params = urlencode({"scrIds": "most_actives", "count": count, "offset": offset})
    data = fetch_json(f"{SCREENER_URL}?{params}")
    result = (((data.get("finance") or {}).get("result") or [{}])[0])
    quotes = result.get("quotes") or []
    return [quote_to_row(quote, offset + index) for index, quote in enumerate(quotes, start=1)], result


def main():
    payload = read_payload()
    count = max(1, min(int(payload.get("count") or 25), 100))
    offset = max(0, int(payload.get("offset") or 0))
    rows = []
    errors = []
    source = "yahoo_screener_api"
    meta = {}

    try:
        rows, meta = fetch_most_active(count, offset)
    except Exception as exc:
        errors.append({"source": "yahoo_screener_api", "error": str(exc)})
        try:
            page_html = fetch_html_fallback(DEFAULT_SOURCE_URL)
            symbols = scrape_symbols_from_html(page_html, count)
            source = "html_symbol_fallback"
            rows = [{"rank": index, "symbol": symbol, "yahoo_url": quote_page(symbol)} for index, symbol in enumerate(symbols, start=1)]
        except Exception as html_exc:
            errors.append({"source": "html_fallback", "error": str(html_exc)})

    print(json.dumps({
        "ok": bool(rows),
        "source_url": DEFAULT_SOURCE_URL,
        "source": source,
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "row_count": len(rows),
        "error_count": len(errors),
        "screener_title": meta.get("title", "Most Actives") if isinstance(meta, dict) else "Most Actives",
        "rows": rows,
        "errors": errors,
        "next_step": "Export rows to Excel, pass them to a manual GPT step, or map selected fields into a CellX table.",
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
