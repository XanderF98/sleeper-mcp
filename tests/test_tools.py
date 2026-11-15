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
    f"/league/{L}": {"settings": {"playoff_week_start": 15, "league_average_match": 1}},
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
    assert report["teams"][0]["team"] == "Bandits"
    assert len(report["teams"]) == 4
    assert "median" in report["how_records_work"]
    assert report["teams"][0]["overall_record"] == "3-3"


def test_team_report_explains_the_median_game():
    report = server.get_team_report("Aces")
    assert "two games every week" in report["how_records_work"]
    assert report["summary"]["overall_record"] == "5-1"


def test_no_median_note_when_the_league_has_no_median_game(monkeypatch):
    responses = dict(RESPONSES)
    responses[f"/league/{L}"] = {"settings": {"playoff_week_start": 15}}
    monkeypatch.setattr(server, "fetch", lambda path, ttl_seconds=60: responses[path])
    report = server.get_luck_report()
    assert "how_records_work" not in report
    assert "overall_record" not in report["teams"][0]


def test_team_report_defaults_to_the_owners_team():
    assert server.get_team_report()["team"] == "Aces"


@pytest.mark.parametrize("owner", ["alice", "ALICE", "u1", "Aces", "aces "])
def test_owner_can_be_a_display_name_user_id_or_team_name(monkeypatch, owner):
    monkeypatch.setattr(server, "OWNER_USERNAME", owner)
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
