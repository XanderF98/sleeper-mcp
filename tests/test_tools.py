"""Run the MCP tools against the made-up league, with Sleeper's API replaced by fixtures."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import server  # noqa: E402
from fixtures import MATCHUPS, ROSTERS, USERS  # noqa: E402

L = server.LEAGUE_ID
RESPONSES = {
    "/state/nfl": {"week": 4, "season_type": "regular"},
    f"/league/{L}": {"settings": {"playoff_week_start": 15}},
    f"/league/{L}/users": USERS,
    f"/league/{L}/rosters": ROSTERS,
    **{f"/league/{L}/matchups/{week}": entries for week, entries in MATCHUPS.items()},
}


@pytest.fixture(autouse=True)
def fake_sleeper(monkeypatch):
    monkeypatch.setattr(server, "fetch", lambda path, ttl_seconds=60: RESPONSES[path])
    monkeypatch.setattr(server, "OWNER_USERNAME", "alice")


def test_week_in_progress_is_left_out():
    # NFL week is 4, so only weeks 1 to 3 count.
    assert {r["week"] for r in server.season_rows()} == {1, 2, 3}


def test_luck_report_tool():
    report = server.get_luck_report()
    assert [t["team"] for t in report][0] == "Bandits"
    assert len(report) == 4


def test_team_report_defaults_to_the_owners_team():
    assert server.get_team_report()["team"] == "Aces"


def test_team_report_by_partial_name():
    assert server.get_team_report("drag")["team"] == "Dragons"


def test_team_report_without_a_known_owner(monkeypatch):
    monkeypatch.setattr(server, "OWNER_USERNAME", None)
    result = server.get_team_report()
    assert "error" in result and "Aces" in result["teams"]


def test_team_report_for_missing_team_lists_the_real_ones():
    result = server.get_team_report("Seahawks")
    assert "error" in result
    assert result["teams"] == ["Aces", "Bandits", "Comets", "Dragons"]


def test_weekly_recap_defaults_to_latest_completed_week():
    assert server.get_weekly_recap()["week"] == 3


def test_matchups_tool_uses_current_week():
    assert server.get_matchups()["week"] == 4


def test_sleeper_outage_gives_a_readable_error(monkeypatch):
    import urllib.error

    monkeypatch.undo()  # use the real fetch, with the network call failing

    def refuse(*args, **kwargs):
        raise urllib.error.URLError("down")

    monkeypatch.setattr(server.urllib.request, "urlopen", refuse)
    server._cache.clear()
    with pytest.raises(RuntimeError, match="Could not reach Sleeper"):
        server.fetch("/state/nfl")
