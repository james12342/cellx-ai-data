from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path

import pandas as pd

from us_options_hot_radar import build_direction_analysis


ROOT = Path(__file__).resolve().parent


def latest(pattern: str, reports: Path) -> Path:
    matches = sorted(reports.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    if not matches:
        raise SystemExit(f"No file found for pattern: {pattern}")
    return matches[0]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build direction analysis from existing options radar CSVs.")
    parser.add_argument("--summary", default=None)
    parser.add_argument("--long", default=None)
    parser.add_argument("--short", default=None)
    parser.add_argument("--out-dir", default="reports")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    reports = ROOT / args.out_dir
    summary_path = Path(args.summary) if args.summary else latest("us_options_summary_*.csv", reports)
    long_path = Path(args.long) if args.long else latest("us_options_hot_long_*.csv", reports)
    short_path = Path(args.short) if args.short else latest("us_options_hot_short_*.csv", reports)

    summary = pd.read_csv(summary_path)
    longs = pd.read_csv(long_path)
    shorts = pd.read_csv(short_path)
    direction = build_direction_analysis(summary, longs, shorts)

    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M")
    out_path = reports / f"us_options_direction_{stamp}.csv"
    direction.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"Direction analysis written: {out_path}")
    print(direction.head(15).to_string(index=False))


if __name__ == "__main__":
    main()
