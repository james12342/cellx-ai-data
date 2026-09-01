from __future__ import annotations

import argparse
import datetime as dt
import math
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Iterable

import pandas as pd
import requests


ROOT = Path(__file__).resolve().parent
REPORTS_DIR = ROOT / "reports"


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


DEFAULT_TICKERS = [
    "SPY",
    "QQQ",
    "IWM",
    "NVDA",
    "TSLA",
    "AAPL",
    "MSFT",
    "AMD",
    "META",
    "AMZN",
    "GOOGL",
    "PLTR",
    "AVGO",
    "SMCI",
    "ARM",
    "MU",
    "NFLX",
    "COIN",
    "MSTR",
    "SOFI",
    "HOOD",
    "RIVN",
    "NIO",
    "BABA",
    "PANW",
    "CRWD",
    "SNOW",
    "ORCL",
    "CRM",
    "JPM",
    "BAC",
    "XOM",
    "CVX",
    "LLY",
    "UNH",
]


NASDAQ_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://www.nasdaq.com",
    "Referer": "https://www.nasdaq.com/",
}


def clean_number(value) -> float:
    if value is None:
        return 0.0
    text = str(value).strip().replace(",", "").replace("$", "")
    if text in {"", "--", "nan", "None"}:
        return 0.0
    try:
        return float(text)
    except ValueError:
        return 0.0


def norm_rank(series: pd.Series, higher_is_better: bool = True) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce").replace([math.inf, -math.inf], pd.NA)
    if values.notna().sum() == 0:
        return pd.Series(0.0, index=series.index)
    pct = values.rank(pct=True, method="average")
    return pct if higher_is_better else 1 - pct


def parse_last_trade(text: str | None) -> float:
    if not text:
        return 0.0
    match = re.search(r"\$([0-9,.]+)", text)
    return clean_number(match.group(1)) if match else 0.0


def parse_expiry_group(text: str | None) -> dt.date | None:
    if not text:
        return None
    for fmt in ("%B %d, %Y", "%b %d, %Y"):
        try:
            return dt.datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def fetch_option_rows(ticker: str, max_days: int, retries: int = 3) -> tuple[pd.DataFrame, float]:
    url = f"https://api.nasdaq.com/api/quote/{ticker}/option-chain"
    params = {
        "assetclass": "stocks",
        "limit": "9999",
    }
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            response = requests.get(url, params=params, headers=NASDAQ_HEADERS, timeout=30)
            response.raise_for_status()
            payload = response.json()
            data = payload.get("data") or {}
            table = data.get("table") or {}
            rows = table.get("rows") or []
            underlying_price = parse_last_trade(data.get("lastTrade"))
            parsed = parse_rows(ticker, rows, underlying_price, max_days)
            return parsed, underlying_price
        except Exception as exc:
            last_error = exc
            time.sleep(1.2 * (attempt + 1))
    raise RuntimeError(f"{ticker}: {last_error}")


def parse_rows(ticker: str, rows: list[dict], underlying_price: float, max_days: int) -> pd.DataFrame:
    today = dt.date.today()
    current_expiry: dt.date | None = None
    parsed: list[dict] = []

    for row in rows:
        expiry_group = parse_expiry_group(row.get("expirygroup"))
        if expiry_group:
            current_expiry = expiry_group
            continue
        if current_expiry is None or row.get("strike") in {None, ""}:
            continue
        dte = (current_expiry - today).days
        if dte < 0 or dte > max_days:
            continue

        strike = clean_number(row.get("strike"))
        for side, prefix in [("CALL", "c"), ("PUT", "p")]:
            last = clean_number(row.get(f"{prefix}_Last"))
            bid = clean_number(row.get(f"{prefix}_Bid"))
            ask = clean_number(row.get(f"{prefix}_Ask"))
            volume = clean_number(row.get(f"{prefix}_Volume"))
            open_interest = clean_number(row.get(f"{prefix}_Openinterest"))
            if volume <= 0 and open_interest <= 0:
                continue
            midpoint = (bid + ask) / 2 if bid > 0 and ask > 0 else last
            notional = volume * max(midpoint, 0.0) * 100
            moneyness = strike / underlying_price if underlying_price else 0.0
            parsed.append(
                {
                    "Ticker": ticker,
                    "Side": side,
                    "Expiration": current_expiry.isoformat(),
                    "DTE": dte,
                    "Strike": strike,
                    "Underlying Price": underlying_price,
                    "Moneyness": moneyness,
                    "Last": last,
                    "Bid": bid,
                    "Ask": ask,
                    "Volume": volume,
                    "Open Interest": open_interest,
                    "Volume/OI": volume / open_interest if open_interest > 0 else volume,
                    "Premium Notional $": notional,
                }
            )

    return pd.DataFrame(parsed)


def fetch_all_options(tickers: Iterable[str], max_days: int, workers: int) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    failures: list[str] = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(fetch_option_rows, ticker.upper(), max_days): ticker.upper() for ticker in tickers}
        for future in as_completed(futures):
            ticker = futures[future]
            try:
                frame, _ = future.result()
                if not frame.empty:
                    frames.append(frame)
            except Exception as exc:
                failures.append(f"{ticker}: {exc}")
    if failures:
        print(f"[warn] {len(failures)} tickers failed: {'; '.join(failures[:8])}")
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def build_contract_scores(options: pd.DataFrame) -> pd.DataFrame:
    if options.empty:
        return options
    frame = options.copy()
    frame["Near Expiry Boost"] = 1 / (frame["DTE"].clip(lower=1) ** 0.35)
    frame["Contract Hot Score"] = (
        norm_rank(frame["Volume"]) * 35
        + norm_rank(frame["Premium Notional $"]) * 25
        + norm_rank(frame["Volume/OI"]) * 20
        + norm_rank(frame["Open Interest"]) * 10
        + norm_rank(frame["Near Expiry Boost"]) * 10
    ).round(2)
    return frame.sort_values("Contract Hot Score", ascending=False).reset_index(drop=True)


def build_ticker_summary(contracts: pd.DataFrame) -> pd.DataFrame:
    if contracts.empty:
        return contracts
    grouped = contracts.pivot_table(
        index="Ticker",
        columns="Side",
        values=["Volume", "Open Interest", "Premium Notional $"],
        aggfunc="sum",
        fill_value=0,
    )
    grouped.columns = [f"{side} {metric}" for metric, side in grouped.columns]
    grouped = grouped.reset_index()

    for col in [
        "CALL Volume",
        "PUT Volume",
        "CALL Open Interest",
        "PUT Open Interest",
        "CALL Premium Notional $",
        "PUT Premium Notional $",
    ]:
        if col not in grouped.columns:
            grouped[col] = 0.0

    grouped["Call/Put Volume"] = grouped["CALL Volume"] / grouped["PUT Volume"].replace(0, pd.NA)
    grouped["Put/Call Volume"] = grouped["PUT Volume"] / grouped["CALL Volume"].replace(0, pd.NA)
    grouped["Call/Put Premium"] = grouped["CALL Premium Notional $"] / grouped["PUT Premium Notional $"].replace(0, pd.NA)
    grouped["Put/Call Premium"] = grouped["PUT Premium Notional $"] / grouped["CALL Premium Notional $"].replace(0, pd.NA)
    grouped = grouped.fillna(0)

    grouped["Long Hot Score"] = (
        norm_rank(grouped["CALL Volume"]) * 30
        + norm_rank(grouped["CALL Premium Notional $"]) * 30
        + norm_rank(grouped["Call/Put Volume"]) * 25
        + norm_rank(grouped["CALL Open Interest"]) * 15
    ).round(2)
    grouped["Short Hot Score"] = (
        norm_rank(grouped["PUT Volume"]) * 30
        + norm_rank(grouped["PUT Premium Notional $"]) * 30
        + norm_rank(grouped["Put/Call Volume"]) * 25
        + norm_rank(grouped["PUT Open Interest"]) * 15
    ).round(2)
    return grouped.sort_values(["Long Hot Score", "Short Hot Score"], ascending=[False, False]).reset_index(drop=True)


def direction_label(score: float) -> str:
    if score >= 12:
        return "Bullish"
    if score <= -12:
        return "Bearish"
    return "Mixed"


def conviction_label(score: float) -> str:
    absolute = abs(score)
    if absolute >= 28:
        return "High"
    if absolute >= 18:
        return "Medium"
    if absolute >= 12:
        return "Low"
    return "Low / unclear"


def watch_action(label: str) -> str:
    if label == "Bullish":
        return "Long-bias watchlist; confirm with price trend and call spread quality."
    if label == "Bearish":
        return "Short/hedge-bias watchlist; confirm with price weakness and put spread quality."
    return "No clean directional edge; treat as two-sided volatility/activity."


def build_direction_analysis(summary: pd.DataFrame, long_contracts: pd.DataFrame, short_contracts: pd.DataFrame) -> pd.DataFrame:
    if summary.empty:
        return summary
    frame = summary.copy()
    frame["Net Direction Score"] = (frame["Long Hot Score"] - frame["Short Hot Score"]).round(2)
    frame["Direction"] = frame["Net Direction Score"].map(direction_label)
    frame["Conviction"] = frame["Net Direction Score"].map(conviction_label)
    frame["Watch Action"] = frame["Direction"].map(watch_action)

    top_calls = (
        long_contracts.sort_values("Contract Hot Score", ascending=False)
        .drop_duplicates("Ticker")
        .set_index("Ticker")
        if not long_contracts.empty
        else pd.DataFrame()
    )
    top_puts = (
        short_contracts.sort_values("Contract Hot Score", ascending=False)
        .drop_duplicates("Ticker")
        .set_index("Ticker")
        if not short_contracts.empty
        else pd.DataFrame()
    )

    def top_contract_text(ticker: str, table: pd.DataFrame) -> str:
        if table.empty or ticker not in table.index:
            return ""
        row = table.loc[ticker]
        return f"{row['Expiration']} {row['Strike']} {row['Side']} score={row['Contract Hot Score']}"

    frame["Top Call Contract"] = frame["Ticker"].map(lambda ticker: top_contract_text(ticker, top_calls))
    frame["Top Put Contract"] = frame["Ticker"].map(lambda ticker: top_contract_text(ticker, top_puts))
    frame["Interpretation"] = frame.apply(
        lambda row: (
            f"{row['Direction']} because Long Hot Score {row['Long Hot Score']:.2f} vs "
            f"Short Hot Score {row['Short Hot Score']:.2f}; "
            f"Call/Put Volume {row['Call/Put Volume']:.2f}, "
            f"Call/Put Premium {row['Call/Put Premium']:.2f}."
        ),
        axis=1,
    )
    columns = [
        "Ticker",
        "Direction",
        "Conviction",
        "Net Direction Score",
        "Long Hot Score",
        "Short Hot Score",
        "Call/Put Volume",
        "Put/Call Volume",
        "Call/Put Premium",
        "Put/Call Premium",
        "CALL Volume",
        "PUT Volume",
        "CALL Premium Notional $",
        "PUT Premium Notional $",
        "Top Call Contract",
        "Top Put Contract",
        "Watch Action",
        "Interpretation",
    ]
    return frame[columns].sort_values("Net Direction Score", ascending=False).reset_index(drop=True)


def write_markdown(summary: pd.DataFrame, longs: pd.DataFrame, shorts: pd.DataFrame, out_path: Path) -> None:
    lines = [
        "# US Options Hot Radar",
        "",
        f"Generated: {dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "> Uses public Nasdaq option-chain data. High call activity is treated as long-interest proxy; high put activity is treated as short/hedge-interest proxy. Not investment advice.",
        "",
        "## Hottest Long Interest",
        "",
        summary.sort_values("Long Hot Score", ascending=False).head(15).to_markdown(index=False) if not summary.empty else "No data.",
        "",
        "## Hottest Short Interest",
        "",
        summary.sort_values("Short Hot Score", ascending=False).head(15).to_markdown(index=False) if not summary.empty else "No data.",
        "",
        "## Direction Read",
        "",
        build_direction_analysis(summary, longs, shorts).head(20).to_markdown(index=False) if not summary.empty else "No direction data.",
        "",
        "## Top Call Contracts",
        "",
        longs.head(20).to_markdown(index=False) if not longs.empty else "No call contracts.",
        "",
        "## Top Put Contracts",
        "",
        shorts.head(20).to_markdown(index=False) if not shorts.empty else "No put contracts.",
        "",
        "## Notes",
        "",
        "- Call volume can include covered-call selling or spread trades; it is a directional proxy, not proof of bullish buying.",
        "- Put volume can include hedging; it is a bearish/hedge proxy, not proof of naked short positioning.",
        "- Premium Notional is estimated from midpoint or last price times contract volume times 100.",
    ]
    out_path.write_text("\n".join(lines), encoding="utf-8")


def parse_tickers(raw: str | None) -> list[str]:
    if not raw:
        return DEFAULT_TICKERS
    return [item.strip().upper() for item in raw.replace(";", ",").split(",") if item.strip()]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="US options hot long/short radar.")
    parser.add_argument("--tickers", default=None, help="Comma-separated ticker list. Defaults to a liquid options watchlist.")
    parser.add_argument("--max-days", type=int, default=45, help="Only include expirations within N calendar days.")
    parser.add_argument("--top-contracts", type=int, default=100, help="Rows to keep for long and short contract CSVs.")
    parser.add_argument("--workers", type=int, default=8, help="Concurrent Nasdaq requests.")
    parser.add_argument("--out-dir", default="reports", help="Output directory. Defaults to the same reports folder.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    tickers = parse_tickers(args.tickers)
    out_dir = ROOT / args.out_dir if not Path(args.out_dir).is_absolute() else Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"[1/4] Fetching option chains for {len(tickers)} tickers...")
    options = fetch_all_options(tickers, max_days=args.max_days, workers=args.workers)
    if options.empty:
        raise SystemExit("No option-chain data fetched.")

    print("[2/4] Scoring option contracts...")
    contracts = build_contract_scores(options)

    print("[3/4] Building ticker long/short summary...")
    summary = build_ticker_summary(contracts)
    long_contracts = contracts[contracts["Side"] == "CALL"].head(args.top_contracts)
    short_contracts = contracts[contracts["Side"] == "PUT"].head(args.top_contracts)
    direction = build_direction_analysis(summary, long_contracts, short_contracts)

    print("[4/4] Writing CSV and Markdown reports...")
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M")
    summary_path = out_dir / f"us_options_summary_{stamp}.csv"
    direction_path = out_dir / f"us_options_direction_{stamp}.csv"
    long_path = out_dir / f"us_options_hot_long_{stamp}.csv"
    short_path = out_dir / f"us_options_hot_short_{stamp}.csv"
    md_path = out_dir / f"us_options_radar_{stamp}.md"

    summary.to_csv(summary_path, index=False, encoding="utf-8-sig")
    direction.to_csv(direction_path, index=False, encoding="utf-8-sig")
    long_contracts.to_csv(long_path, index=False, encoding="utf-8-sig")
    short_contracts.to_csv(short_path, index=False, encoding="utf-8-sig")
    write_markdown(summary, long_contracts, short_contracts, md_path)

    print("")
    print("Done.")
    print(f"- {summary_path}")
    print(f"- {direction_path}")
    print(f"- {long_path}")
    print(f"- {short_path}")
    print(f"- {md_path}")


if __name__ == "__main__":
    main()
