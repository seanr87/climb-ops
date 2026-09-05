#!/usr/bin/env python3
"""Pull Sleeper league data into data/ as a Claude-ready digest.

Read-only, no auth. Resolves league by username + season so you never
need to hunt for the league ID. Run locally or via GitHub Actions.
"""

import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

USERNAME = "seanroreilly87"
SEASON = "2026"
LEAGUE_NAME = "The Climb"  # used to pick the right league if you're in several
SPORT = "nfl"
BASE = "https://api.sleeper.app/v1"
DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# Positions worth keeping when we slim the giant players database
KEEP_POS = {"QB", "RB", "WR", "TE", "K", "DEF"}


def get(url: str):
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.load(r)


def resolve_league():
    user = get(f"{BASE}/user/{USERNAME}")
    leagues = get(f"{BASE}/user/{user['user_id']}/leagues/{SPORT}/{SEASON}")
    for lg in leagues:
        if lg["name"] == LEAGUE_NAME:
            return user, lg
    if len(leagues) == 1:
        return user, leagues[0]
    names = [lg["name"] for lg in leagues]
    sys.exit(f"League '{LEAGUE_NAME}' not found. Available: {names}")


def slim_players(players: dict) -> dict:
    """The full player DB is ~5 MB; keep only fantasy-relevant fields."""
    slim = {}
    for pid, p in players.items():
        if not isinstance(p, dict) or p.get("position") not in KEEP_POS:
            continue
        slim[pid] = {
            "name": p.get("full_name") or f"{p.get('first_name','')} {p.get('last_name','')}".strip(),
            "pos": p.get("position"),
            "team": p.get("team"),
            "status": p.get("status"),
            "injury_status": p.get("injury_status"),
            "injury_note": p.get("injury_body_part"),
        }
    return slim


def main():
    DATA_DIR.mkdir(exist_ok=True)
    now = datetime.now(timezone.utc)

    user, league = resolve_league()
    lid = league["league_id"]

    state = get(f"{BASE}/state/{SPORT}")           # current NFL week
    week = state.get("week") or 1

    rosters = get(f"{BASE}/league/{lid}/rosters")
    users = get(f"{BASE}/league/{lid}/users")
    matchups = get(f"{BASE}/league/{lid}/matchups/{week}")
    transactions = get(f"{BASE}/league/{lid}/transactions/{week}")
    trending_add = get(f"{BASE}/players/{SPORT}/trending/add?lookback_hours=24&limit=50")
    trending_drop = get(f"{BASE}/players/{SPORT}/trending/drop?lookback_hours=24&limit=50")
    players = slim_players(get(f"{BASE}/players/{SPORT}"))

    # Map roster_id -> display name, and find Sean's roster
    owner_by_roster = {}
    display = {u["user_id"]: u.get("display_name", "?") for u in users}
    my_roster = None
    for r in rosters:
        owner_by_roster[r["roster_id"]] = display.get(r.get("owner_id"), "?")
        if r.get("owner_id") == user["user_id"]:
            my_roster = r

    digest = {
        "pulled_at_utc": now.isoformat(timespec="seconds"),
        "nfl_week": week,
        "league": {"id": lid, "name": league["name"], "scoring": league.get("scoring_settings"),
                   "roster_positions": league.get("roster_positions")},
        "my_roster": my_roster,
        "owner_by_roster_id": owner_by_roster,
        "matchups_this_week": matchups,
        "transactions_this_week": transactions,
        "trending_adds_24h": trending_add,
        "trending_drops_24h": trending_drop,
    }

    (DATA_DIR / "digest.json").write_text(json.dumps(digest, indent=1))
    (DATA_DIR / "players_slim.json").write_text(json.dumps(players, indent=1))

    # Human/Claude-readable summary
    def pname(pid):
        p = players.get(str(pid), {})
        tag = f" [{p.get('injury_status')}]" if p.get("injury_status") else ""
        return f"{p.get('name', pid)} ({p.get('pos','?')}-{p.get('team','FA')}){tag}"

    lines = [
        f"# Sleeper digest — {league['name']}",
        f"Pulled: {now.strftime('%Y-%m-%d %H:%M UTC')} · NFL week {week}",
        "",
        "## My roster",
    ]
    if my_roster:
        for pid in my_roster.get("players") or []:
            starter = " (STARTER)" if pid in (my_roster.get("starters") or []) else ""
            lines.append(f"- {pname(pid)}{starter}")
    lines += ["", "## Trending adds (24h, all Sleeper)"]
    for t in trending_add[:25]:
        lines.append(f"- {pname(t['player_id'])} — {t['count']:,} adds")
    lines += ["", "## League transactions this week"]
    for tx in transactions[:30]:
        adds = ", ".join(pname(p) for p in (tx.get("adds") or {}))
        drops = ", ".join(pname(p) for p in (tx.get("drops") or {}))
        lines.append(f"- {tx['type']} ({tx['status']}): +[{adds}] -[{drops}]")

    (DATA_DIR / "digest.md").write_text("\n".join(lines) + "\n")
    print(f"OK: week {week}, {len(players)} players, wrote data/digest.json, players_slim.json, digest.md")


if __name__ == "__main__":
    main()
