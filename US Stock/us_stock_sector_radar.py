from __future__ import annotations

import argparse
import datetime as dt
import math
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Iterable

import pandas as pd
import requests


LOCAL_CACHE_DIR = Path(__file__).resolve().parent / ".cache" / "yfinance"
LOCAL_CACHE_DIR.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("YFINANCE_CACHE_DIR", str(LOCAL_CACHE_DIR))

try:
    import yfinance as yf
except ImportError as exc:  # pragma: no cover - friendly CLI failure
    raise SystemExit(
        "Missing dependency: yfinance. Install with `pip install -r requirements.txt`."
    ) from exc

try:
    yf.set_tz_cache_location(str(LOCAL_CACHE_DIR))
except Exception:
    pass


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


SECTOR_ETFS = {
    "Semiconductors": "SMH",
    "Software": "IGV",
    "Cybersecurity": "HACK",
    "AI & Robotics": "BOTZ",
    "Communication Services": "XLC",
    "Consumer Discretionary": "XLY",
    "Consumer Staples": "XLP",
    "Energy": "XLE",
    "Financials": "XLF",
    "Healthcare": "XLV",
    "Industrials": "XLI",
    "Materials": "XLB",
    "Real Estate": "XLRE",
    "Technology": "XLK",
    "Utilities": "XLU",
}


SECTOR_UNIVERSE = {
    "Semiconductors": ["NVDA", "AMD", "AVGO", "TSM", "ASML", "QCOM", "MU", "ARM", "MRVL", "SMCI"],
    "Software": ["MSFT", "ORCL", "CRM", "NOW", "ADBE", "PANW", "CRWD", "SNOW", "DDOG", "PLTR"],
    "Cybersecurity": ["PANW", "CRWD", "FTNT", "ZS", "OKTA", "NET", "S", "TENB"],
    "AI & Robotics": ["NVDA", "PLTR", "ISRG", "ROK", "TER", "PATH", "SYM", "IRBT"],
    "Communication Services": ["GOOGL", "META", "NFLX", "DIS", "TMUS", "VZ", "T", "SPOT"],
    "Consumer Discretionary": ["AMZN", "TSLA", "HD", "MCD", "NKE", "SBUX", "BKNG", "LOW"],
    "Consumer Staples": ["COST", "WMT", "PG", "KO", "PEP", "PM", "MDLZ", "TGT"],
    "Energy": ["XOM", "CVX", "COP", "SLB", "EOG", "MPC", "PSX", "OXY"],
    "Financials": ["JPM", "BAC", "WFC", "GS", "MS", "V", "MA", "AXP", "BLK"],
    "Healthcare": ["LLY", "UNH", "JNJ", "MRK", "ABBV", "TMO", "ISRG", "VRTX"],
    "Industrials": ["GE", "CAT", "RTX", "HON", "BA", "DE", "LMT", "ETN"],
    "Materials": ["LIN", "SHW", "FCX", "NEM", "APD", "ECL", "DD", "DOW"],
    "Real Estate": ["PLD", "AMT", "EQIX", "WELL", "SPG", "O", "PSA", "DLR"],
    "Technology": ["AAPL", "MSFT", "NVDA", "AVGO", "AMD", "ORCL", "CRM", "ADBE", "NOW", "PLTR"],
    "Utilities": ["NEE", "SO", "DUK", "CEG", "AEP", "SRE", "D", "EXC"],
}


def norm_rank(series: pd.Series, higher_is_better: bool = True) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce").replace([math.inf, -math.inf], pd.NA)
    if values.notna().sum() == 0:
        return pd.Series(0.0, index=series.index)
    pct = values.rank(pct=True, method="average")
    return pct if higher_is_better else 1 - pct


def pct_change(close: pd.Series, days: int) -> float:
    close = close.dropna()
    if len(close) <= days:
        return float("nan")
    return (close.iloc[-1] / close.iloc[-days - 1] - 1) * 100


def latest_volume_spike(volume: pd.Series, window: int = 20) -> float:
    volume = volume.dropna()
    if len(volume) <= window:
        return float("nan")
    avg = volume.iloc[-window - 1 : -1].mean()
    if not avg:
        return float("nan")
    return volume.iloc[-1] / avg


def fetch_yahoo_chart(ticker: str, period: str) -> pd.DataFrame:
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
    params = {"range": period, "interval": "1d"}
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, params=params, headers=headers, timeout=20)
    response.raise_for_status()
    payload = response.json()
    result = payload.get("chart", {}).get("result") or []
    if not result:
        raise RuntimeError(payload.get("chart", {}).get("error") or "empty Yahoo chart result")
    item = result[0]
    timestamps = item.get("timestamp") or []
    quote = (item.get("indicators", {}).get("quote") or [{}])[0]
    adjusted = (item.get("indicators", {}).get("adjclose") or [{}])[0]
    close = adjusted.get("adjclose") or quote.get("close") or []
    volume = quote.get("volume") or []
    if not timestamps or not close:
        raise RuntimeError("missing timestamp or close data")
    frame = pd.DataFrame(
        {
            "Close": close,
            "Volume": volume,
        },
        index=pd.to_datetime(timestamps, unit="s").normalize(),
    )
    return frame.dropna(subset=["Close"])


def download_prices_direct(tickers: Iterable[str], period: str = "3mo") -> pd.DataFrame:
    ticker_list = sorted(set(tickers))
    frames: dict[str, pd.DataFrame] = {}
    failures: list[str] = []
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(fetch_yahoo_chart, ticker, period): ticker for ticker in ticker_list}
        for future in as_completed(futures):
            ticker = futures[future]
            try:
                frame = future.result()
                if not frame.empty:
                    frames[ticker] = frame
            except Exception as exc:
                failures.append(f"{ticker}: {exc}")
    if not frames:
        raise RuntimeError("No Yahoo chart data downloaded. " + "; ".join(failures[:5]))
    if failures:
        print(f"[warn] {len(failures)} tickers failed from Yahoo chart; continuing with available data.")
    return pd.concat(frames, axis=1)


def download_prices_yfinance(tickers: Iterable[str], period: str = "3mo") -> pd.DataFrame:
    ticker_list = sorted(set(tickers))
    for attempt in range(3):
        try:
            data = yf.download(
                tickers=ticker_list,
                period=period,
                interval="1d",
                group_by="ticker",
                auto_adjust=True,
                progress=False,
                threads=True,
            )
            if not data.empty:
                return data
        except Exception as exc:
            last_error = exc
        time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"Failed to download Yahoo Finance prices: {last_error}")


def download_prices(tickers: Iterable[str], period: str = "3mo") -> pd.DataFrame:
    try:
        return download_prices_direct(tickers, period=period)
    except Exception as direct_error:
        print(f"[warn] Yahoo chart API failed, trying yfinance: {direct_error}")
        return download_prices_yfinance(tickers, period=period)


def ticker_frame(data: pd.DataFrame, ticker: str) -> pd.DataFrame:
    if isinstance(data.columns, pd.MultiIndex):
        if ticker not in data.columns.get_level_values(0):
            return pd.DataFrame()
        return data[ticker].dropna(how="all")
    return data.dropna(how="all")


def build_sector_scores(price_data: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for sector, etf in SECTOR_ETFS.items():
        frame = ticker_frame(price_data, etf)
        if frame.empty or "Close" not in frame:
            continue
        close = frame["Close"]
        volume = frame.get("Volume", pd.Series(dtype=float))
        rows.append(
            {
                "Sector": sector,
                "Proxy ETF": etf,
                "1D %": pct_change(close, 1),
                "5D %": pct_change(close, 5),
                "20D %": pct_change(close, 20),
                "Volume Spike": latest_volume_spike(volume),
                "Last Close": close.dropna().iloc[-1],
            }
        )
    sectors = pd.DataFrame(rows)
    if sectors.empty:
        return sectors
    sectors["Sector Heat Score"] = (
        norm_rank(sectors["1D %"]) * 25
        + norm_rank(sectors["5D %"]) * 25
        + norm_rank(sectors["20D %"]) * 20
        + norm_rank(sectors["Volume Spike"]) * 20
        + norm_rank(sectors["Last Close"]) * 10
    ).round(2)
    return sectors.sort_values("Sector Heat Score", ascending=False).reset_index(drop=True)


def load_institution_file(path: str | None) -> pd.DataFrame:
    if not path:
        return pd.DataFrame(columns=["Ticker", "Institution Signal", "Institution Detail"])
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"Institution file not found: {file_path}")
    frame = pd.read_csv(file_path)
    ticker_col = next((c for c in frame.columns if c.lower() in {"ticker", "symbol"}), None)
    score_col = next((c for c in frame.columns if c.lower() in {"score", "institution_score", "shares_change_pct"}), None)
    detail_col = next((c for c in frame.columns if c.lower() in {"detail", "institution", "manager"}), None)
    if ticker_col is None:
        raise ValueError("Institution file needs a ticker or symbol column.")
    out = pd.DataFrame({"Ticker": frame[ticker_col].astype(str).str.upper()})
    out["Institution Signal"] = pd.to_numeric(frame[score_col], errors="coerce").fillna(0) if score_col else 0
    out["Institution Detail"] = frame[detail_col].astype(str) if detail_col else ""
    return out


def build_leaders(
    sectors: pd.DataFrame,
    price_data: pd.DataFrame,
    institution_signals: pd.DataFrame,
    top_sectors: int,
    leaders_per_sector: int,
) -> pd.DataFrame:
    rows = []
    institution_signals = institution_signals.drop_duplicates("Ticker", keep="last")
    inst_map = institution_signals.set_index("Ticker") if not institution_signals.empty else pd.DataFrame()

    for _, sector_row in sectors.head(top_sectors).iterrows():
        sector = sector_row["Sector"]
        proxy = sector_row["Proxy ETF"]
        sector_5d = sector_row["5D %"]
        for ticker in SECTOR_UNIVERSE.get(sector, []):
            frame = ticker_frame(price_data, ticker)
            if frame.empty or "Close" not in frame:
                continue
            close = frame["Close"]
            volume = frame.get("Volume", pd.Series(dtype=float))
            one_d = pct_change(close, 1)
            five_d = pct_change(close, 5)
            twenty_d = pct_change(close, 20)
            dollar_volume = (close.dropna().iloc[-1] * volume.dropna().iloc[-1]) / 1_000_000 if len(volume.dropna()) else float("nan")
            inst_score = 0
            inst_detail = ""
            if not inst_map.empty and ticker in inst_map.index:
                inst_score = inst_map.loc[ticker, "Institution Signal"]
                inst_detail = inst_map.loc[ticker, "Institution Detail"]
            rows.append(
                {
                    "Sector": sector,
                    "Proxy ETF": proxy,
                    "Sector Heat Score": sector_row["Sector Heat Score"],
                    "Ticker": ticker,
                    "1D %": one_d,
                    "5D %": five_d,
                    "20D %": twenty_d,
                    "Relative 5D %": five_d - sector_5d,
                    "Volume Spike": latest_volume_spike(volume),
                    "Dollar Volume $M": dollar_volume,
                    "Institution Signal": inst_score,
                    "Institution Detail": inst_detail,
                }
            )

    leaders = pd.DataFrame(rows)
    if leaders.empty:
        return leaders
    leaders["Leader Score"] = (
        norm_rank(leaders["Relative 5D %"]) * 25
        + norm_rank(leaders["1D %"]) * 15
        + norm_rank(leaders["20D %"]) * 15
        + norm_rank(leaders["Volume Spike"]) * 20
        + norm_rank(leaders["Dollar Volume $M"]) * 15
        + norm_rank(leaders["Institution Signal"]) * 10
    ).round(2)
    return (
        leaders.sort_values(["Sector Heat Score", "Leader Score"], ascending=[False, False])
        .groupby("Sector", as_index=False, group_keys=False)
        .head(leaders_per_sector)
        .reset_index(drop=True)
    )


def write_markdown(sectors: pd.DataFrame, leaders: pd.DataFrame, out_path: Path) -> None:
    lines = [
        "# US Stock Sector Radar",
        "",
        f"Generated: {dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "> Public market data only. This is for watchlist research, not investment advice.",
        "",
        "## Hot Sectors",
        "",
        sectors.head(15).to_markdown(index=False) if not sectors.empty else "No sector data.",
        "",
        "## Leader Candidates",
        "",
        leaders.to_markdown(index=False) if not leaders.empty else "No leader candidates.",
        "",
        "## Notes",
        "",
        "- US markets do not disclose an A-share-style daily institution seat list.",
        "- The sector signal uses ETF momentum and volume as a tradable proxy for active money.",
        "- Institution Signal is optional. Provide a CSV from 13F/whale-tracking data if you want that factor included.",
    ]
    out_path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="US stock sector and leader radar.")
    parser.add_argument("--top-sectors", type=int, default=8, help="Analyze top N hot sectors.")
    parser.add_argument("--leaders-per-sector", type=int, default=3, help="Output N leaders per sector.")
    parser.add_argument("--period", default="3mo", help="Yahoo Finance price period, e.g. 1mo, 3mo, 6mo.")
    parser.add_argument("--institution-file", default=None, help="Optional CSV with ticker/symbol and score columns.")
    parser.add_argument("--out-dir", default="reports", help="Output directory.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    all_tickers = set(SECTOR_ETFS.values())
    for tickers in SECTOR_UNIVERSE.values():
        all_tickers.update(tickers)

    print("[1/4] Downloading ETF and stock price data...")
    price_data = download_prices(all_tickers, period=args.period)

    print("[2/4] Scoring sectors...")
    sectors = build_sector_scores(price_data)

    print("[3/4] Loading optional institution signals...")
    institution_signals = load_institution_file(args.institution_file)

    print("[4/4] Scoring leader candidates...")
    leaders = build_leaders(
        sectors,
        price_data,
        institution_signals,
        top_sectors=args.top_sectors,
        leaders_per_sector=args.leaders_per_sector,
    )

    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M")
    sectors_path = out_dir / f"us_sectors_{stamp}.csv"
    leaders_path = out_dir / f"us_leaders_{stamp}.csv"
    md_path = out_dir / f"us_radar_{stamp}.md"

    sectors.to_csv(sectors_path, index=False, encoding="utf-8-sig")
    leaders.to_csv(leaders_path, index=False, encoding="utf-8-sig")
    write_markdown(sectors, leaders, md_path)

    print("")
    print("Done.")
    print(f"- {sectors_path}")
    print(f"- {leaders_path}")
    print(f"- {md_path}")


if __name__ == "__main__":
    main()
