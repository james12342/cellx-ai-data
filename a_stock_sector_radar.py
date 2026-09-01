from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import sys
import time
from pathlib import Path
from typing import Iterable

import pandas as pd


try:
    import akshare as ak
except ImportError as exc:  # pragma: no cover - friendly CLI failure
    raise SystemExit(
        "Missing dependency: akshare. Install with `pip install -r requirements.txt`."
    ) from exc


MONEY_UNIT = 100_000_000

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def pick_col(df: pd.DataFrame, candidates: Iterable[str], required: bool = True) -> str | None:
    """Find a likely column by exact name first, then by ordered substring match."""
    cols = [str(c) for c in df.columns]
    for name in candidates:
        if name in cols:
            return name
    for name in candidates:
        parts = [p for p in name.replace("/", " ").split() if p]
        if not parts:
            parts = [name]
        for col in cols:
            if all(part in col for part in parts):
                return col
    if required:
        raise KeyError(f"Cannot find any of columns {list(candidates)} in {cols}")
    return None


def to_num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(
        series.astype(str)
        .str.replace(",", "", regex=False)
        .str.replace("%", "", regex=False)
        .str.replace("--", "", regex=False),
        errors="coerce",
    )


def money_text_to_yi(series: pd.Series) -> pd.Series:
    text = series.astype(str).str.replace(",", "", regex=False).str.strip()
    sign = text.str.contains("-", regex=False).map({True: -1, False: 1})
    numeric = pd.to_numeric(
        text.str.replace("-", "", regex=False)
        .str.replace("亿", "", regex=False)
        .str.replace("万", "", regex=False)
        .str.replace("元", "", regex=False)
        .str.replace("--", "", regex=False),
        errors="coerce",
    )
    unit = pd.Series(1.0, index=series.index)
    unit[text.str.contains("万", regex=False)] = 0.0001
    unit[text.str.contains("元", regex=False)] = 1 / MONEY_UNIT
    return numeric * sign * unit


def norm_rank(series: pd.Series, higher_is_better: bool = True) -> pd.Series:
    values = to_num(series).replace([math.inf, -math.inf], pd.NA)
    if values.notna().sum() == 0:
        return pd.Series(0.0, index=series.index)
    pct = values.rank(pct=True, method="average")
    return pct if higher_is_better else 1 - pct


def retry_call(label: str, func, attempts: int = 3, sleep_seconds: float = 1.2):
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            return func()
        except Exception as exc:
            last_error = exc
            if attempt < attempts - 1:
                print(f"[warn] {label} failed, retrying ({attempt + 1}/{attempts})...")
                time.sleep(sleep_seconds * (attempt + 1))
    raise RuntimeError(f"{label} failed after {attempts} attempts: {last_error}") from last_error


def today_yyyymmdd() -> str:
    return dt.date.today().strftime("%Y%m%d")


def iter_dates(end_date: str, days: int) -> list[str]:
    end = dt.datetime.strptime(end_date, "%Y%m%d").date()
    return [(end - dt.timedelta(days=i)).strftime("%Y%m%d") for i in range(days)]


def fetch_sector_fund_flow(sector_type: str) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for indicator in ["今日", "5日", "10日"]:
        frame = retry_call(
            f"{sector_type}/{indicator}",
            lambda indicator=indicator, sector_type=sector_type: ak.stock_sector_fund_flow_rank(
                indicator=indicator,
                sector_type=sector_type,
            ),
        )
        frame = frame.copy()
        frame["资金周期"] = indicator
        frame["板块类型"] = "行业" if "行业" in sector_type else "概念"
        frames.append(frame)
    return pd.concat(frames, ignore_index=True)


def build_sector_scores_from_fallback() -> pd.DataFrame:
    """Fallback path when Eastmoney sector fund-flow endpoints are unavailable."""
    fund = retry_call("同花顺行业资金流", lambda: ak.stock_fund_flow_industry())
    spot = retry_call("新浪行业板块行情", lambda: ak.stock_sector_spot("行业"))

    fund = fund.copy()
    spot = spot.copy()
    board_col = pick_col(fund, ["行业", "板块"])
    net_col = pick_col(fund, ["净额", "净流入"])
    change_col = pick_col(fund, ["行业-涨跌幅", "涨跌幅"])
    lead_col = pick_col(fund, ["领涨股"], required=False)

    label_col = pick_col(spot, ["label"])
    spot_board_col = pick_col(spot, ["板块"])
    amount_col = pick_col(spot, ["总成交额"], required=False)

    frame = pd.DataFrame(
        {
            "板块类型": "行业",
            "板块名称": fund[board_col].astype(str),
            "今日主力净流入_亿": to_num(fund[net_col]),
            "5日主力净流入_亿": 0,
            "10日主力净流入_亿": 0,
            "板块涨跌幅_%": to_num(fund[change_col]),
            "领涨股": fund[lead_col].astype(str) if lead_col else "",
        }
    )
    label_frame = pd.DataFrame(
        {
            "板块名称": spot[spot_board_col].astype(str),
            "成分标识": spot[label_col].astype(str),
            "板块成交额_亿": to_num(spot[amount_col]) / MONEY_UNIT if amount_col else 0,
        }
    )
    frame = frame.merge(label_frame, on="板块名称", how="left")
    frame["资金连续性"] = (frame["今日主力净流入_亿"] > 0).astype(int)
    frame["板块热度分"] = (
        norm_rank(frame["今日主力净流入_亿"]) * 55
        + norm_rank(frame["板块涨跌幅_%"]) * 25
        + norm_rank(frame["板块成交额_亿"].fillna(0)) * 10
        + norm_rank(frame["资金连续性"]) * 10
    ).round(2)
    keep = [
        "板块类型",
        "板块名称",
        "成分标识",
        "领涨股",
        "板块热度分",
        "今日主力净流入_亿",
        "5日主力净流入_亿",
        "10日主力净流入_亿",
        "板块涨跌幅_%",
        "资金连续性",
    ]
    return frame[keep].sort_values("板块热度分", ascending=False).reset_index(drop=True)


def build_sector_scores(include_concepts: bool) -> pd.DataFrame:
    types = ["行业资金流"]
    if include_concepts:
        types.append("概念资金流")

    try:
        raw = pd.concat([fetch_sector_fund_flow(t) for t in types], ignore_index=True)
    except Exception as exc:
        print(f"[warn] 东方财富板块资金接口不可用，切换到同花顺/新浪行业数据: {exc}")
        return build_sector_scores_from_fallback()
    name_col = pick_col(raw, ["名称", "板块名称"])
    change_col = pick_col(raw, ["今日涨跌幅", "涨跌幅"], required=False)
    net_col = pick_col(raw, ["今日主力净流入-净额", "今日主力净流入", "主力净流入"], required=False)
    five_col = pick_col(raw, ["5日主力净流入-净额", "5日主力净流入", "5日净流入"], required=False)
    ten_col = pick_col(raw, ["10日主力净流入-净额", "10日主力净流入", "10日净流入"], required=False)

    today_df = raw[raw["资金周期"] == "今日"].copy()
    five_df = raw[raw["资金周期"] == "5日"][[name_col] + ([five_col] if five_col else [])].copy()
    ten_df = raw[raw["资金周期"] == "10日"][[name_col] + ([ten_col] if ten_col else [])].copy()

    if five_col:
        today_df = today_df.merge(five_df, on=name_col, how="left", suffixes=("", "_5日"))
        five_col = f"{five_col}_5日" if five_col in today_df.columns and f"{five_col}_5日" in today_df.columns else five_col
    if ten_col:
        today_df = today_df.merge(ten_df, on=name_col, how="left", suffixes=("", "_10日"))
        ten_col = f"{ten_col}_10日" if ten_col in today_df.columns and f"{ten_col}_10日" in today_df.columns else ten_col

    today_df["今日主力净流入_亿"] = to_num(today_df[net_col]) / MONEY_UNIT if net_col else 0
    today_df["5日主力净流入_亿"] = to_num(today_df[five_col]) / MONEY_UNIT if five_col else 0
    today_df["10日主力净流入_亿"] = to_num(today_df[ten_col]) / MONEY_UNIT if ten_col else 0
    today_df["板块涨跌幅_%"] = to_num(today_df[change_col]) if change_col else 0
    today_df["资金连续性"] = (
        (today_df["今日主力净流入_亿"] > 0).astype(int)
        + (today_df["5日主力净流入_亿"] > 0).astype(int)
        + (today_df["10日主力净流入_亿"] > 0).astype(int)
    )

    today_df["板块热度分"] = (
        norm_rank(today_df["今日主力净流入_亿"]) * 45
        + norm_rank(today_df["5日主力净流入_亿"]) * 20
        + norm_rank(today_df["10日主力净流入_亿"]) * 10
        + norm_rank(today_df["板块涨跌幅_%"]) * 15
        + norm_rank(today_df["资金连续性"]) * 10
    ).round(2)

    today_df = today_df.rename(columns={name_col: "板块名称"})
    keep = ["板块类型", "板块名称", "板块热度分", "今日主力净流入_亿", "5日主力净流入_亿", "10日主力净流入_亿", "板块涨跌幅_%", "资金连续性"]
    if "成分标识" in today_df.columns:
        keep.insert(2, "成分标识")
    return today_df[keep].sort_values("板块热度分", ascending=False).reset_index(drop=True)


def normalize_sina_members(raw: pd.DataFrame) -> pd.DataFrame:
    raw = raw.copy()
    out = pd.DataFrame(
        {
            "代码": raw["code"].astype(str).str.zfill(6),
            "名称": raw["name"].astype(str),
            "涨跌幅": to_num(raw["changepercent"]),
            "换手率": to_num(raw["turnoverratio"]),
            "成交额": to_num(raw["amount"]),
        }
    )
    return out


def get_board_members(board_name: str, board_type: str, member_symbol: str | None = None) -> pd.DataFrame:
    if member_symbol and member_symbol.lower() not in {"nan", "none", "null"}:
        return normalize_sina_members(
            retry_call(f"新浪成分股/{board_name}", lambda: ak.stock_sector_detail(member_symbol))
        )

    last_error: Exception | None = None
    for attempt in range(3):
        try:
            if board_type == "行业":
                return ak.stock_board_industry_cons_em(symbol=board_name)
            return ak.stock_board_concept_cons_em(symbol=board_name)
        except Exception as exc:
            last_error = exc
            time.sleep(0.8 * (attempt + 1))
    raise RuntimeError(f"{last_error}")


def build_institution_signals(date: str, lookback_days: int) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for day in iter_dates(date, lookback_days):
        try:
            frame = ak.stock_lhb_jgmmtj_em(start_date=day, end_date=day)
        except Exception:
            continue
        if frame is None or frame.empty:
            continue
        frame = frame.copy()
        frame["龙虎榜日期"] = day
        frames.append(frame)
    if not frames:
        return pd.DataFrame(columns=["代码", "名称", "龙虎榜日期", "机构净买入_亿", "机构买入_亿", "机构卖出_亿"])

    raw = pd.concat(frames, ignore_index=True)
    code_col = pick_col(raw, ["代码", "股票代码"])
    name_col = pick_col(raw, ["名称", "股票名称"])
    net_col = pick_col(raw, ["机构买入净额", "机构净买入额", "机构净买入"], required=False)
    buy_col = pick_col(raw, ["机构买入总额", "机构买入额", "买入额"], required=False)
    sell_col = pick_col(raw, ["机构卖出总额", "机构卖出额", "卖出额"], required=False)

    out = pd.DataFrame(
        {
            "代码": raw[code_col].astype(str).str.zfill(6),
            "名称": raw[name_col].astype(str),
            "龙虎榜日期": raw["龙虎榜日期"],
            "机构净买入_亿": to_num(raw[net_col]) / MONEY_UNIT if net_col else 0,
            "机构买入_亿": to_num(raw[buy_col]) / MONEY_UNIT if buy_col else 0,
            "机构卖出_亿": to_num(raw[sell_col]) / MONEY_UNIT if sell_col else 0,
        }
    )
    return out.sort_values(["龙虎榜日期", "机构净买入_亿"], ascending=[False, False]).reset_index(drop=True)


def build_stock_fund_rank() -> pd.DataFrame:
    try:
        raw = retry_call("个股资金流排名/今日", lambda: ak.stock_individual_fund_flow_rank(indicator="今日"))
    except Exception as exc:
        print(f"[warn] 东方财富个股资金接口不可用，切换到同花顺个股资金数据: {exc}")
        raw = retry_call("同花顺个股资金流", lambda: ak.stock_fund_flow_individual())
        code_col = pick_col(raw, ["股票代码", "代码"])
        name_col = pick_col(raw, ["股票简称", "名称"])
        net_col = pick_col(raw, ["净额", "净流入"])
        change_col = pick_col(raw, ["涨跌幅"], required=False)
        return pd.DataFrame(
            {
                "代码": raw[code_col].astype(str).str.zfill(6),
                "名称": raw[name_col].astype(str),
                "个股主力净流入_亿": money_text_to_yi(raw[net_col]),
                "个股涨跌幅_%": to_num(raw[change_col]) if change_col else 0,
            }
        )

    code_col = pick_col(raw, ["代码"])
    name_col = pick_col(raw, ["名称"])
    net_col = pick_col(raw, ["今日主力净流入-净额", "今日主力净流入", "主力净流入"], required=False)
    change_col = pick_col(raw, ["今日涨跌幅", "涨跌幅"], required=False)
    out = pd.DataFrame(
        {
            "代码": raw[code_col].astype(str).str.zfill(6),
            "名称": raw[name_col].astype(str),
            "个股主力净流入_亿": to_num(raw[net_col]) / MONEY_UNIT if net_col else 0,
            "个股涨跌幅_%": to_num(raw[change_col]) if change_col else 0,
        }
    )
    return out


def build_leaders(
    sectors: pd.DataFrame,
    stock_funds: pd.DataFrame,
    institutions: pd.DataFrame,
    top_sectors: int,
    leaders_per_sector: int,
) -> pd.DataFrame:
    results: list[pd.DataFrame] = []
    inst_latest = institutions.sort_values("龙虎榜日期").drop_duplicates("代码", keep="last")

    for _, sector in sectors.head(top_sectors).iterrows():
        board_name = str(sector["板块名称"])
        board_type = str(sector["板块类型"])
        member_symbol = str(sector.get("成分标识", "") or "")
        try:
            members = get_board_members(board_name, board_type, member_symbol=member_symbol)
        except Exception as exc:
            print(f"[warn] Cannot fetch board members for {board_type}:{board_name}: {exc}")
            lead_name = str(sector.get("领涨股", "") or "")
            if not lead_name or lead_name.lower() in {"nan", "none", "null"}:
                continue
            lead = stock_funds[stock_funds["名称"] == lead_name].copy()
            if lead.empty:
                continue
            lead["板块类型"] = board_type
            lead["板块名称"] = board_name
            lead["板块热度分"] = sector["板块热度分"]
            lead["个股涨跌幅_%"] = lead.get("个股涨跌幅_%", 0)
            lead["换手率_%"] = 0
            lead["成交额_亿"] = 0
            lead = lead.merge(inst_latest, on=["代码", "名称"], how="left")
            lead[["机构净买入_亿", "机构买入_亿", "机构卖出_亿"]] = lead[
                ["机构净买入_亿", "机构买入_亿", "机构卖出_亿"]
            ].fillna(0)
            lead["机构龙虎榜"] = lead["龙虎榜日期"].fillna("").astype(str)
            lead["龙头候选分"] = (
                60
                + norm_rank(lead["个股主力净流入_亿"]) * 20
                + norm_rank(lead["机构净买入_亿"]) * 20
            ).round(2)
            results.append(lead.head(1))
            continue
        if members is None or members.empty:
            continue

        code_col = pick_col(members, ["代码"])
        name_col = pick_col(members, ["名称"])
        change_col = pick_col(members, ["涨跌幅"], required=False)
        turnover_col = pick_col(members, ["换手率"], required=False)
        amount_col = pick_col(members, ["成交额"], required=False)

        frame = pd.DataFrame(
            {
                "板块类型": board_type,
                "板块名称": board_name,
                "板块热度分": sector["板块热度分"],
                "代码": members[code_col].astype(str).str.zfill(6),
                "名称": members[name_col].astype(str),
                "个股涨跌幅_%": to_num(members[change_col]) if change_col else 0,
                "换手率_%": to_num(members[turnover_col]) if turnover_col else 0,
                "成交额_亿": to_num(members[amount_col]) / MONEY_UNIT if amount_col else 0,
            }
        )
        frame = frame.merge(stock_funds[["代码", "个股主力净流入_亿"]], on="代码", how="left")
        frame = frame.merge(inst_latest, on=["代码", "名称"], how="left")
        frame[["个股主力净流入_亿", "机构净买入_亿", "机构买入_亿", "机构卖出_亿"]] = frame[
            ["个股主力净流入_亿", "机构净买入_亿", "机构买入_亿", "机构卖出_亿"]
        ].fillna(0)
        frame["机构龙虎榜"] = frame["龙虎榜日期"].fillna("").astype(str)
        frame["龙头候选分"] = (
            norm_rank(frame["个股主力净流入_亿"]) * 30
            + norm_rank(frame["个股涨跌幅_%"]) * 25
            + norm_rank(frame["成交额_亿"]) * 15
            + norm_rank(frame["换手率_%"]) * 10
            + norm_rank(frame["机构净买入_亿"]) * 20
        ).round(2)
        results.append(frame.sort_values("龙头候选分", ascending=False).head(leaders_per_sector))

    if not results:
        return pd.DataFrame()
    keep = [
        "板块类型",
        "板块名称",
        "板块热度分",
        "代码",
        "名称",
        "龙头候选分",
        "个股涨跌幅_%",
        "个股主力净流入_亿",
        "机构净买入_亿",
        "机构龙虎榜",
        "换手率_%",
        "成交额_亿",
    ]
    return pd.concat(results, ignore_index=True)[keep].sort_values(
        ["板块热度分", "龙头候选分"], ascending=[False, False]
    )


def write_markdown(sectors: pd.DataFrame, leaders: pd.DataFrame, institutions: pd.DataFrame, out_path: Path) -> None:
    lines = [
        "# A股板块资金雷达",
        "",
        f"生成时间：{dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "> 数据来自公开行情与龙虎榜接口，适合观察活跃资金线索，不构成投资建议。",
        "",
        "## 活跃板块 Top 10",
        "",
        sectors.head(10).to_markdown(index=False),
        "",
        "## 龙头候选",
        "",
        leaders.to_markdown(index=False) if not leaders.empty else "暂无候选结果。",
        "",
        "## 机构龙虎榜净买入 Top 20",
        "",
        institutions.head(20).to_markdown(index=False) if not institutions.empty else "最近窗口内暂无机构龙虎榜数据。",
        "",
        "## 读法",
        "",
        "- 优先看“板块热度分”靠前且 5 日/10 日资金仍为正的方向。",
        "- 龙头候选不是买入建议，只是把资金、涨幅、成交、换手、机构龙虎榜叠加排序。",
        "- “机构龙虎榜”只代表龙虎榜机构专用席位，不覆盖所有机构交易。",
    ]
    out_path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="A-share sector money-flow radar.")
    parser.add_argument("--date", default=today_yyyymmdd(), help="龙虎榜查询截止日期，格式 YYYYMMDD。默认今天。")
    parser.add_argument("--lookback-days", type=int, default=7, help="龙虎榜机构席位回看自然日数量。")
    parser.add_argument("--top-sectors", type=int, default=12, help="分析前 N 个高热度板块。")
    parser.add_argument("--leaders-per-sector", type=int, default=3, help="每个板块输出 N 只龙头候选。")
    parser.add_argument("--industry-only", action="store_true", help="只看行业板块，不看概念板块。")
    parser.add_argument("--out-dir", default="reports", help="输出目录。")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        print("[1/4] Fetching sector fund-flow rankings...")
        sectors = build_sector_scores(include_concepts=not args.industry_only)

        print("[2/4] Fetching individual stock fund-flow ranking...")
        stock_funds = build_stock_fund_rank()

        print("[3/4] Fetching institution LHB signals...")
        institutions = build_institution_signals(args.date, args.lookback_days)

        print("[4/4] Scoring sector leaders...")
        leaders = build_leaders(sectors, stock_funds, institutions, args.top_sectors, args.leaders_per_sector)
    except (RuntimeError, json.JSONDecodeError) as exc:
        raise SystemExit(
            "Data fetch failed. The public Eastmoney/AKShare endpoint may be throttled, changed, "
            f"or temporarily returning a bad gateway response.\nDetail: {exc}"
        ) from exc

    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M")
    sectors_path = out_dir / f"sectors_{stamp}.csv"
    leaders_path = out_dir / f"leaders_{stamp}.csv"
    inst_path = out_dir / f"institutions_{stamp}.csv"
    md_path = out_dir / f"radar_{stamp}.md"

    sectors.to_csv(sectors_path, index=False, encoding="utf-8-sig")
    leaders.to_csv(leaders_path, index=False, encoding="utf-8-sig")
    institutions.to_csv(inst_path, index=False, encoding="utf-8-sig")
    write_markdown(sectors, leaders, institutions, md_path)

    print("")
    print("Done.")
    print(f"- {sectors_path}")
    print(f"- {leaders_path}")
    print(f"- {inst_path}")
    print(f"- {md_path}")


if __name__ == "__main__":
    main()
