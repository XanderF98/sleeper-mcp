"""Sleeper fantasy football MCP server.

Exposes a Sleeper league's public, read-only data as MCP tools that an AI agent
(for example a Copilot Studio agent) can call.

Run locally:   python server.py
Endpoint:      http://localhost:8000/mcp   (Streamable HTTP transport)

Requires:      pip install "mcp>=2"
"""

import json
import os
import time
import urllib.request

from mcp.server.mcpserver import MCPServer

SLEEPER_API = "https://api.sleeper.app/v1"
LEAGUE_ID = os.environ.get("SLEEPER_LEAGUE_ID", "1389689066286489600")

mcp = MCPServer(
    "sleeper-league",
    instructions=(
        "Read-only data for one Sleeper fantasy football league: standings, "
        "weekly matchups, and team rosters."
    ),
)

# Small in-memory cache so repeated questions don't hammer Sleeper's API.
_cache: dict[str, tuple[float, object]] = {}


def fetch(path: str, ttl_seconds: int = 60):
    """GET a Sleeper API path and return the parsed JSON, cached for ttl_seconds."""
    now = time.time()
    hit = _cache.get(path)
    if hit and now - hit[0] < ttl_seconds:
        return hit[1]
    request = urllib.request.Request(
        f"{SLEEPER_API}{path}", headers={"User-Agent": "sleeper-mcp-demo"}
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        data = json.load(response)
    _cache[path] = (now, data)
    return data


def team_names() -> dict[int, str]:
    """Map each roster_id to a readable team name."""
    users = {u["user_id"]: u for u in fetch(f"/league/{LEAGUE_ID}/users")}
    names = {}
    for roster in fetch(f"/league/{LEAGUE_ID}/rosters"):
        user = users.get(roster.get("owner_id"), {})
        custom = (user.get("metadata") or {}).get("team_name")
        names[roster["roster_id"]] = (
            custom or user.get("display_name") or f"Team {roster['roster_id']}"
        )
    return names


def player_label(player_id: str) -> str:
    """Turn a Sleeper player id into 'Name (POS, TEAM)'."""
    # The full player list is large (several MB), so cache it for a day.
    players = fetch("/players/nfl", ttl_seconds=86400)
    p = players.get(str(player_id))
    if not p:
        return str(player_id)  # team defenses use ids like "SEA"
    name = p.get("full_name") or f"{p.get('first_name', '')} {p.get('last_name', '')}".strip()
    return f"{name} ({p.get('position', '?')}, {p.get('team') or 'FA'})"


def current_week() -> int:
    return int(fetch("/state/nfl").get("week") or 1)


@mcp.tool()
def get_standings() -> list[dict]:
    """League standings: every team's wins, losses, ties, points for and points against, best record first."""
    names = team_names()
    table = []
    for roster in fetch(f"/league/{LEAGUE_ID}/rosters"):
        s = roster.get("settings") or {}
        table.append(
            {
                "team": names[roster["roster_id"]],
                "wins": s.get("wins", 0),
                "losses": s.get("losses", 0),
                "ties": s.get("ties", 0),
                "points_for": s.get("fpts", 0) + s.get("fpts_decimal", 0) / 100,
                "points_against": s.get("fpts_against", 0) + s.get("fpts_against_decimal", 0) / 100,
            }
        )
    table.sort(key=lambda t: (t["wins"], t["points_for"]), reverse=True)
    return table


@mcp.tool()
def get_matchups(week: int | None = None) -> dict:
    """Head-to-head matchups and scores for a week. Leave week empty for the current NFL week."""
    week = week or current_week()
    names = team_names()
    games: dict[int, list[dict]] = {}
    for entry in fetch(f"/league/{LEAGUE_ID}/matchups/{week}"):
        games.setdefault(entry.get("matchup_id") or 0, []).append(
            {"team": names.get(entry["roster_id"], "?"), "points": entry.get("points", 0)}
        )
    return {"week": week, "matchups": [games[k] for k in sorted(games)]}


@mcp.tool()
def get_roster(team: str) -> dict:
    """One team's starters and bench. `team` is a team name or part of one (case-insensitive)."""
    names = team_names()
    matches = [rid for rid, name in names.items() if team.lower() in name.lower()]
    if len(matches) != 1:
        return {"error": f"Expected one team matching '{team}'.", "teams": sorted(names.values())}
    roster = next(r for r in fetch(f"/league/{LEAGUE_ID}/rosters") if r["roster_id"] == matches[0])
    starters = [p for p in (roster.get("starters") or []) if p and p != "0"]
    bench = [p for p in (roster.get("players") or []) if p not in starters]
    return {
        "team": names[matches[0]],
        "starters": [player_label(p) for p in starters],
        "bench": [player_label(p) for p in bench],
    }


if __name__ == "__main__":
    # 0.0.0.0 so a hosting service can reach it; PORT is set by most hosts.
    mcp.run(
        transport="streamable-http",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "8000")),
        stateless_http=True,
    )
