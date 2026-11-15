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
import urllib.error
import urllib.request

from mcp.server.auth.settings import AuthSettings
from mcp.server.mcpserver import MCPServer

import luck
from auth import EntraTokenVerifier

SLEEPER_API = "https://api.sleeper.app/v1"
LEAGUE_ID = os.environ.get("SLEEPER_LEAGUE_ID", "1389689066286489600")
# Optional: who "my team" refers to. A Sleeper display name, user ID, or team name.
OWNER_USERNAME = os.environ.get("SLEEPER_USERNAME")

# OAuth is switched on by setting these three environment variables. With them
# unset the server runs without authentication, which is fine for local testing.
ENTRA_TENANT_ID = os.environ.get("ENTRA_TENANT_ID")          # the organization's directory ID
ENTRA_API_CLIENT_ID = os.environ.get("ENTRA_API_CLIENT_ID")  # this server's app registration
PUBLIC_URL = os.environ.get("PUBLIC_URL")                    # e.g. https://my-server.onrender.com
REQUIRED_SCOPE = "league.read"


def auth_config() -> dict:
    """Build the MCPServer auth arguments, or none if OAuth is not configured."""
    if not (ENTRA_TENANT_ID and ENTRA_API_CLIENT_ID and PUBLIC_URL):
        return {}
    return {
        "token_verifier": EntraTokenVerifier(ENTRA_TENANT_ID, ENTRA_API_CLIENT_ID),
        "auth": AuthSettings(
            issuer_url=f"https://login.microsoftonline.com/{ENTRA_TENANT_ID}/v2.0",
            resource_server_url=f"{PUBLIC_URL.rstrip('/')}/mcp",
            required_scopes=[REQUIRED_SCOPE],
            # The verifier checks the token's audience itself.
            validate_token_resource=False,
        ),
    }


mcp = MCPServer(
    "sleeper-league",
    instructions=(
        "Read-only data for one Sleeper fantasy football league: standings, weekly "
        "matchups, team rosters, and luck analysis (who the schedule has helped or hurt)."
    ),
    **auth_config(),
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
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            data = json.load(response)
    except (urllib.error.URLError, TimeoutError) as error:
        # Raised errors reach the agent as text, so say something it can relay.
        raise RuntimeError("Could not reach Sleeper's API. Try again in a minute.") from error
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


def find_team(team: str | None) -> tuple[int | None, dict[int, str]]:
    """Resolve a team name (or part of one) to its roster_id.

    With no name given, falls back to the team owned by SLEEPER_USERNAME.
    Returns (roster_id or None, all team names by roster_id).
    """
    names = team_names()
    if team:
        matches = [rid for rid, name in names.items() if team.lower() in name.lower()]
        return (matches[0] if len(matches) == 1 else None), names
    if OWNER_USERNAME:
        # Accept a Sleeper display name, a user ID, or the team's name.
        wanted = OWNER_USERNAME.strip().lower()
        owner_ids = {
            u["user_id"]
            for u in fetch(f"/league/{LEAGUE_ID}/users")
            if wanted in ((u.get("display_name") or "").lower(), str(u.get("user_id")))
        }
        for roster in fetch(f"/league/{LEAGUE_ID}/rosters"):
            if roster.get("owner_id") in owner_ids or names[roster["roster_id"]].lower() == wanted:
                return roster["roster_id"], names
    return None, names


def season_rows() -> list[dict]:
    """One row per team per completed regular-season week (see luck.weekly_rows)."""
    state = fetch("/state/nfl")
    settings = fetch(f"/league/{LEAGUE_ID}", ttl_seconds=3600).get("settings") or {}
    regular_season_end = int(settings.get("playoff_week_start") or 15) - 1
    # The week in progress is left out: half-played scores would skew everything.
    last_played = int(state.get("week") or 1) - 1 if state.get("season_type") == "regular" else regular_season_end
    last_week = min(last_played, regular_season_end)
    matchups = {
        week: fetch(f"/league/{LEAGUE_ID}/matchups/{week}", ttl_seconds=6 * 3600)
        for week in range(1, last_week + 1)
    }
    return luck.weekly_rows(matchups, team_names())


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
    roster_id, names = find_team(team)
    if roster_id is None:
        return {"error": f"Expected one team matching '{team}'.", "teams": sorted(names.values())}
    roster = next(r for r in fetch(f"/league/{LEAGUE_ID}/rosters") if r["roster_id"] == roster_id)
    starters = [p for p in (roster.get("starters") or []) if p and p != "0"]
    bench = [p for p in (roster.get("players") or []) if p not in starters]
    return {
        "team": names[roster_id],
        "starters": [player_label(p) for p in starters],
        "bench": [player_label(p) for p in bench],
    }


@mcp.tool()
def get_luck_report() -> list[dict]:
    """Which teams the schedule has helped or hurt this season, luckiest first.

    For each team: its real head-to-head record, the wins it would expect from its
    scores alone, the difference (luck: positive is lucky, negative is unlucky), its
    all-play record against the whole league, and its record against the weekly median.
    Use this for questions about luck, who is better or worse than their record, or
    who has had the hardest schedule. Covers completed regular-season weeks only.
    """
    return luck.luck_table(season_rows())


@mcp.tool()
def get_team_report(team: str | None = None) -> dict:
    """Why one team's season is going the way it is: week-by-week scores, weekly rank,
    opponent, result, and bench points, plus a summary with luck and league averages.

    `team` is a team name or part of one. Leave it empty for the user's own team
    ("my team", "how am I doing", "why am I losing").
    """
    roster_id, names = find_team(team)
    if roster_id is None:
        problem = f"Expected one team matching '{team}'." if team else "I don't know which team is yours. Ask with a team name."
        return {"error": problem, "teams": sorted(names.values())}
    return luck.team_report(season_rows(), names[roster_id])


@mcp.tool()
def get_weekly_recap(week: int | None = None) -> dict:
    """The stories of one completed week: highest and lowest score, biggest blowout,
    closest game, the highest score that still lost, and the lowest score that won.
    Leave week empty for the most recent completed week.
    """
    rows = season_rows()
    if not rows:
        return {"error": "No completed weeks yet this season."}
    return luck.weekly_recap(rows, week or max(r["week"] for r in rows))


if __name__ == "__main__":
    # 0.0.0.0 so a hosting service can reach it; PORT is set by most hosts.
    mcp.run(
        transport="streamable-http",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "8000")),
        stateless_http=True,
    )
