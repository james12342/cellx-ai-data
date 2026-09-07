#!/usr/bin/env python3
import csv
import io
import json
import re
import sys
from datetime import datetime, timezone


DEFAULT_ROSTER_TARGETS = {
    "QB": 1,
    "RB": 2,
    "WR": 2,
    "TE": 1,
    "FLEX": 1,
    "K": 1,
    "DST": 1,
    "BENCH": 6,
}


SAMPLE_RANKINGS = [
    ("Ja'Marr Chase", "WR", "CIN", 1, 1, 337, 10, "Elite WR1 in PPR formats"),
    ("Bijan Robinson", "RB", "ATL", 2, 1, 326, 5, "High-volume RB with receiving upside"),
    ("Justin Jefferson", "WR", "MIN", 3, 1, 322, 6, "Elite target earner"),
    ("CeeDee Lamb", "WR", "DAL", 4, 1, 318, 10, "Top-tier WR with weekly ceiling"),
    ("Amon-Ra St. Brown", "WR", "DET", 5, 1, 309, 8, "Reliable PPR production"),
    ("Breece Hall", "RB", "NYJ", 6, 1, 296, 9, "Three-down RB upside"),
    ("Jahmyr Gibbs", "RB", "DET", 7, 1, 292, 8, "Explosive RB with receiving role"),
    ("Puka Nacua", "WR", "LAR", 8, 2, 287, 8, "Strong volume profile"),
    ("A.J. Brown", "WR", "PHI", 9, 2, 282, 9, "High-ceiling WR1"),
    ("Saquon Barkley", "RB", "PHI", 10, 2, 279, 9, "Elite offense and touchdown upside"),
    ("Malik Nabers", "WR", "NYG", 11, 2, 273, 11, "Alpha receiver upside"),
    ("Nico Collins", "WR", "HOU", 12, 2, 268, 6, "Efficient WR with strong offense"),
    ("De'Von Achane", "RB", "MIA", 13, 2, 263, 12, "Explosive upside, some role risk"),
    ("Garrett Wilson", "WR", "NYJ", 14, 2, 260, 9, "Strong target share projection"),
    ("Jonathan Taylor", "RB", "IND", 15, 2, 258, 11, "Workhorse RB profile"),
    ("Drake London", "WR", "ATL", 16, 3, 252, 5, "Breakout WR profile"),
    ("Marvin Harrison Jr.", "WR", "ARI", 17, 3, 248, 8, "Talent-driven upside"),
    ("Josh Allen", "QB", "BUF", 18, 1, 374, 7, "Elite rushing and passing QB"),
    ("Lamar Jackson", "QB", "BAL", 19, 1, 361, 7, "Elite dual-threat QB"),
    ("Trey McBride", "TE", "ARI", 20, 1, 228, 8, "Top TE target share"),
    ("Brock Bowers", "TE", "LV", 21, 1, 222, 8, "High-volume TE upside"),
    ("Jayden Daniels", "QB", "WAS", 22, 2, 348, 12, "Rushing ceiling QB"),
    ("Jalen Hurts", "QB", "PHI", 23, 2, 345, 9, "Elite TD upside"),
    ("Kenneth Walker III", "RB", "SEA", 24, 3, 225, 8, "Strong early-down profile"),
    ("Mike Evans", "WR", "TB", 25, 4, 229, 9, "Touchdown and red-zone role"),
    ("George Kittle", "TE", "SF", 26, 2, 206, 14, "Efficient TE with spike weeks"),
    ("DK Metcalf", "WR", "SEA", 27, 4, 224, 8, "Big-play WR profile"),
    ("James Cook", "RB", "BUF", 28, 3, 219, 7, "Efficient RB in strong offense"),
    ("Deebo Samuel", "WR", "WAS", 29, 5, 218, 12, "Versatile usage"),
    ("Rashee Rice", "WR", "KC", 30, 5, 216, 10, "High-volume offense fit"),
    ("Mark Andrews", "TE", "BAL", 31, 3, 198, 7, "Proven TE touchdown role"),
    ("Tee Higgins", "WR", "CIN", 32, 5, 213, 10, "Strong offense and TD upside"),
    ("Joe Burrow", "QB", "CIN", 33, 3, 326, 10, "Stackable pocket passer"),
    ("Kyren Williams", "RB", "LAR", 34, 4, 211, 8, "Volume-based RB"),
    ("DJ Moore", "WR", "CHI", 35, 6, 208, 5, "Strong WR2 profile"),
    ("Courtland Sutton", "WR", "DEN", 36, 6, 201, 12, "Red-zone role"),
    ("David Montgomery", "RB", "DET", 37, 4, 198, 8, "Stable touchdown role"),
    ("Calvin Ridley", "WR", "TEN", 38, 7, 196, 10, "Downfield upside"),
    ("Evan Engram", "TE", "DEN", 39, 4, 184, 12, "PPR TE floor"),
    ("Patrick Mahomes", "QB", "KC", 40, 4, 318, 10, "Elite offense QB"),
    ("San Francisco 49ers", "DST", "SF", 120, 1, 150, 14, "Top defensive unit"),
    ("Dallas Cowboys", "DST", "DAL", 121, 1, 146, 10, "Pressure and turnover upside"),
    ("Justin Tucker", "K", "BAL", 130, 1, 142, 7, "Reliable kicker profile"),
    ("Brandon Aubrey", "K", "DAL", 131, 1, 140, 10, "Strong offense kicker"),
]


def read_payload():
    raw = sys.stdin.read().strip() or "{}"
    try:
        return json.loads(raw)
    except Exception:
        return {}


def normalize_name(value):
    return re.sub(r"[^a-z0-9]", "", str(value or "").lower())


def split_names(value):
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [part.strip() for part in re.split(r"[\n,;]+", str(value or "")) if part.strip()]


def parse_rankings_csv(text):
    if not text:
        return []
    rows = []
    reader = csv.DictReader(io.StringIO(text))
    for index, raw in enumerate(reader, start=1):
        name = raw.get("name") or raw.get("player") or raw.get("Player") or raw.get("Name")
        if not name:
            continue
        rows.append({
            "name": name.strip(),
            "position": (raw.get("position") or raw.get("pos") or raw.get("Position") or "FLEX").strip().upper(),
            "team": (raw.get("team") or raw.get("Team") or "").strip(),
            "rank": int(float(raw.get("rank") or raw.get("adp") or index)),
            "tier": int(float(raw.get("tier") or 9)),
            "projected_points": float(raw.get("projected_points") or raw.get("points") or raw.get("projection") or 0),
            "bye": str(raw.get("bye") or ""),
            "notes": raw.get("notes") or raw.get("Notes") or "Imported ranking row",
        })
    return rows


def sample_rankings():
    return [
        {
            "name": name,
            "position": position,
            "team": team,
            "rank": rank,
            "tier": tier,
            "projected_points": points,
            "bye": bye,
            "notes": notes,
        }
        for name, position, team, rank, tier, points, bye, notes in SAMPLE_RANKINGS
    ]


def roster_counts(roster_names, rankings):
    by_name = {normalize_name(player["name"]): player for player in rankings}
    counts = {}
    matched = []
    for name in roster_names:
        player = by_name.get(normalize_name(name))
        if player:
            position = player["position"]
            counts[position] = counts.get(position, 0) + 1
            matched.append(player)
    return counts, matched


def position_need(position, counts, targets):
    if position in ("K", "DST"):
        return -8 if counts.get(position, 0) >= targets.get(position, 1) else -2
    if position in ("RB", "WR"):
        base_target = targets.get(position, 2)
        if counts.get(position, 0) < base_target:
            return 14
        if counts.get("RB", 0) + counts.get("WR", 0) + counts.get("TE", 0) < base_target + targets.get("FLEX", 1) + 2:
            return 5
        return 0
    if position in ("QB", "TE"):
        return 10 if counts.get(position, 0) < targets.get(position, 1) else -5
    return 0


def recommendation_reason(player, counts, targets, pick_number):
    reasons = []
    position = player["position"]
    if position in ("RB", "WR") and counts.get(position, 0) < targets.get(position, 2):
        reasons.append(f"fills starting {position} need")
    elif position in ("QB", "TE") and counts.get(position, 0) < targets.get(position, 1):
        reasons.append(f"fills starting {position} slot")
    if player["rank"] <= pick_number + 8:
        reasons.append("good value near current pick")
    if player["tier"] <= 2:
        reasons.append("top-tier option")
    if not reasons:
        reasons.append("best available depth/value")
    return "; ".join(reasons)


def recommend(payload):
    rankings = parse_rankings_csv(payload.get("rankings_csv") or "") or sample_rankings()
    drafted_names = split_names(payload.get("drafted_players") or payload.get("draftedPlayers") or [])
    my_roster_names = split_names(payload.get("my_roster") or payload.get("myRoster") or [])
    pick_number = int(payload.get("pick_number") or payload.get("pickNumber") or len(drafted_names) + 1)
    top_n = max(1, min(int(payload.get("recommendation_count") or 10), 25))
    league_format = payload.get("scoring") or "PPR"
    targets = dict(DEFAULT_ROSTER_TARGETS)
    targets.update(payload.get("roster_targets") or {})

    drafted = {normalize_name(name) for name in drafted_names}
    available = [player for player in rankings if normalize_name(player["name"]) not in drafted]
    counts, matched_roster = roster_counts(my_roster_names, rankings)

    recs = []
    for player in available:
        rank_value = max(0, 150 - player["rank"])
        points_value = float(player.get("projected_points") or 0) / 10
        need_value = position_need(player["position"], counts, targets)
        tier_bonus = max(0, 8 - int(player.get("tier") or 8)) * 3
        too_early_penalty = max(0, player["rank"] - pick_number - 30) * 0.15
        score = round(rank_value + points_value + need_value + tier_bonus - too_early_penalty, 2)
        recs.append({
            "rank": len(recs) + 1,
            "player": player["name"],
            "position": player["position"],
            "team": player["team"],
            "overall_rank": player["rank"],
            "tier": player["tier"],
            "projected_points": player["projected_points"],
            "bye": player["bye"],
            "draft_score": score,
            "recommendation": recommendation_reason(player, counts, targets, pick_number),
            "notes": player["notes"],
        })

    recs.sort(key=lambda item: (-item["draft_score"], item["overall_rank"]))
    for index, row in enumerate(recs, start=1):
        row["rank"] = index

    available_rows = []
    for index, player in enumerate(sorted(available, key=lambda item: item["rank"]), start=1):
        available_rows.append({
            "rank": index,
            "player": player["name"],
            "position": player["position"],
            "team": player["team"],
            "overall_rank": player["rank"],
            "tier": player["tier"],
            "projected_points": player["projected_points"],
            "bye": player["bye"],
            "notes": player["notes"],
        })

    return {
        "ok": True,
        "mode": "manual_pick_entry",
        "league_format": league_format,
        "pick_number": pick_number,
        "drafted_count": len(drafted_names),
        "my_roster_count": len(my_roster_names),
        "available_count": len(available_rows),
        "roster_needs": [
            {
                "position": position,
                "current": counts.get(position, 0),
                "target": targets.get(position, 0),
                "need": max(0, targets.get(position, 0) - counts.get(position, 0)),
            }
            for position in ("QB", "RB", "WR", "TE", "FLEX", "K", "DST")
        ],
        "recommendations": recs[:top_n],
        "rows": recs[:top_n],
        "available_players": available_rows,
        "my_roster": matched_roster,
        "message": "Paste updated drafted_players after each real pick, then rerun the node for fresh recommendations.",
    }


def main():
    payload = read_payload()
    result = recommend(payload)
    result["provider"] = "Cell AI Data Fantasy Draft MVP"
    result["generated_at"] = datetime.now(timezone.utc).isoformat()
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
