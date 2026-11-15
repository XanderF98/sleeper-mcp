"""Check the luck maths against a small league worked out by hand (see fixtures.py)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import luck  # noqa: E402
from fixtures import MATCHUPS, NAMES  # noqa: E402

ROWS = luck.weekly_rows(MATCHUPS, NAMES)


def by_team(table):
    return {line["team"]: line for line in table}


def test_unplayed_week_is_skipped():
    assert {r["week"] for r in ROWS} == {1, 2, 3}
    assert len(ROWS) == 12


def test_all_play_counts_every_other_team():
    week1 = {r["team"]: r for r in ROWS if r["week"] == 1}
    assert week1["Comets"]["all_play_wins"] == 3   # top score beats all three others
    assert week1["Aces"]["all_play_wins"] == 2
    assert week1["Dragons"]["all_play_wins"] == 0


def test_luck_table_matches_hand_calculation():
    table = by_team(luck.luck_table(ROWS))

    # Aces: outscored 2/3, 2/3 and 3/3 of the league, so expected 2.3 wins; actually won 2.
    assert table["Aces"]["head_to_head_record"] == "2-1"
    assert table["Aces"]["expected_head_to_head_wins"] == 2.3
    assert table["Aces"]["luck"] == -0.3
    assert table["Aces"]["all_play_record"] == "7-2"
    assert table["Aces"]["median_record"] == "3-0"
    assert table["Aces"]["points_per_week"] == 108.3
    assert table["Aces"]["opponent_points_per_week"] == 95.0

    # Bandits: same 2-1 record from much weaker scores, so they are the lucky ones.
    assert table["Bandits"]["head_to_head_record"] == "2-1"
    assert table["Bandits"]["expected_head_to_head_wins"] == 1.3
    assert table["Bandits"]["luck"] == 0.7
    assert table["Bandits"]["all_play_record"] == "4-5"
    assert table["Bandits"]["median_record"] == "1-2"

    # Dragons: last every week. Nothing lucky or unlucky about 0-3.
    assert table["Dragons"]["head_to_head_record"] == "0-3"
    assert table["Dragons"]["luck"] == 0.0


def test_luckiest_team_comes_first():
    assert luck.luck_table(ROWS)[0]["team"] == "Bandits"


def test_expected_wins_add_up_to_games_played():
    # Every game has exactly one winner, so expected wins across the league equal the games played.
    table = luck.luck_table(ROWS)
    assert round(sum(t["expected_head_to_head_wins"] for t in table)) == 6
    assert round(sum(t["luck"] for t in table), 1) == 0.1  # zero, give or take rounding


def test_team_report_finds_the_unlucky_loss():
    report = luck.team_report(ROWS, "Aces")
    summary = report["summary"]
    assert summary["weeks_lost_with_a_top_half_score"] == [2]
    assert summary["weeks_won_with_a_bottom_half_score"] == []
    assert summary["best_week"] == {"week": 3, "points": 130.0}
    assert summary["worst_week"] == {"week": 2, "points": 95.0}
    assert summary["average_weekly_rank"] == 1.7
    assert summary["league_average_points_per_week"] == 95.4
    assert report["weeks"][0]["bench_points"] == 12.5
    assert [w["result"] for w in report["weeks"]] == ["W", "L", "W"]


def test_team_report_for_unknown_team():
    assert "error" in luck.team_report(ROWS, "Nobody")


def test_weekly_recap():
    recap = luck.weekly_recap(ROWS, 2)
    assert recap["highest_score"] == {"team": "Comets", "points": 110.0}
    assert recap["lowest_score"] == {"team": "Dragons", "points": 60.0}
    assert recap["biggest_blowout"]["winner"] == "Comets" and recap["biggest_blowout"]["margin"] == 15.0
    assert recap["closest_game"]["winner"] == "Bandits" and recap["closest_game"]["margin"] == 10.0
    assert recap["highest_score_that_lost"] == {"team": "Aces", "points": 95.0, "rank_that_week": 2}
    assert recap["lowest_score_that_won"] == {"team": "Bandits", "points": 70.0, "rank_that_week": 3}


def test_recap_for_unplayed_week():
    assert "error" in luck.weekly_recap(ROWS, 4)
