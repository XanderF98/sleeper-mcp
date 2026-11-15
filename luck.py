"""Luck analysis for a fantasy league, worked out from weekly scores.

The idea: your record depends on who you happened to play. Your score doesn't.
So for every week, compare each team's score against every other team's score,
not only its scheduled opponent's.

  All-play record   How a team would have done playing every other team each week.
  Expected wins     The head-to-head wins a team "deserved": each week, the share
                    of the league it outscored.
  Luck              Actual head-to-head wins minus expected wins. Positive means
                    the schedule helped; negative means it hurt.

This league also plays the league median each week (a second result, won by
finishing in the top half). That result depends only on your own score, so it
is reported separately and left out of the luck number.

Everything here is plain functions over plain data, so it can be tested without
calling Sleeper.
"""

from collections import defaultdict


def weekly_rows(matchups_by_week: dict[int, list[dict]], names: dict[int, str]) -> list[dict]:
    """Flatten Sleeper's matchup data into one row per team per completed week.

    Weeks where nobody has scored yet are skipped.
    """
    rows = []
    for week in sorted(matchups_by_week):
        entries = matchups_by_week[week]
        if not entries or not any(e.get("points") for e in entries):
            continue

        by_matchup: dict[int, list[dict]] = defaultdict(list)
        for entry in entries:
            if entry.get("matchup_id") is not None:
                by_matchup[entry["matchup_id"]].append(entry)

        scores = sorted((e.get("points") or 0.0 for e in entries), reverse=True)
        for entry in entries:
            points = entry.get("points") or 0.0
            pair = by_matchup.get(entry.get("matchup_id"), [])
            opponent = next((o for o in pair if o["roster_id"] != entry["roster_id"]), None)

            starters = set(entry.get("starters") or [])
            player_points = entry.get("players_points") or {}
            bench_points = sum(pts or 0.0 for pid, pts in player_points.items() if pid not in starters)

            beaten = sum(1 for s in scores if s < points)
            tied = sum(1 for s in scores if s == points) - 1  # don't count the team itself
            rows.append(
                {
                    "week": week,
                    "roster_id": entry["roster_id"],
                    "team": names.get(entry["roster_id"], f"Team {entry['roster_id']}"),
                    "points": round(points, 2),
                    "rank_that_week": scores.index(points) + 1,
                    "teams_that_week": len(scores),
                    "all_play_wins": beaten + tied / 2,
                    "beat_median": scores.index(points) + 1 <= len(scores) // 2,
                    "opponent": names.get(opponent["roster_id"]) if opponent else None,
                    "opponent_points": round(opponent.get("points") or 0.0, 2) if opponent else None,
                    "bench_points": round(bench_points, 2),
                }
            )
    return rows


def _result(row: dict) -> str | None:
    """'W', 'L' or 'T' for the head-to-head game, or None if there was no opponent."""
    if row["opponent_points"] is None:
        return None
    if row["points"] > row["opponent_points"]:
        return "W"
    if row["points"] < row["opponent_points"]:
        return "L"
    return "T"


def luck_table(rows: list[dict], median_game: bool = False) -> list[dict]:
    """One line per team, luckiest first.

    With median_game on, each team's overall record counts both weekly results:
    the head-to-head game and the game against the league median.
    """
    by_team: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_team[row["team"]].append(row)

    table = []
    for team, weeks in by_team.items():
        results = [_result(w) for w in weeks]
        h2h_wins = results.count("W") + results.count("T") / 2
        h2h_games = sum(1 for r in results if r)
        expected = sum(w["all_play_wins"] / (w["teams_that_week"] - 1) for w in weeks if _result(w))
        all_play_wins = sum(w["all_play_wins"] for w in weeks)
        all_play_games = sum(w["teams_that_week"] - 1 for w in weeks)
        median_wins = sum(1 for w in weeks if w["beat_median"])
        median_losses = len(weeks) - median_wins
        line = {"team": team}
        if median_game:
            line["overall_record"] = (
                f"{results.count('W') + median_wins}-{results.count('L') + median_losses}"
                + (f"-{results.count('T')}" if results.count("T") else "")
            )
        line.update(
            {
                "head_to_head_record": f"{results.count('W')}-{results.count('L')}"
                + (f"-{results.count('T')}" if results.count("T") else ""),
                "expected_head_to_head_wins": round(expected, 1),
                "luck": round(h2h_wins - expected, 1),
                "all_play_record": f"{all_play_wins:g}-{all_play_games - all_play_wins:g}",
                "all_play_win_pct": round(100 * all_play_wins / all_play_games) if all_play_games else 0,
                "median_record": f"{median_wins}-{median_losses}",
                "points_per_week": round(sum(w["points"] for w in weeks) / len(weeks), 1),
                "opponent_points_per_week": round(
                    sum(w["opponent_points"] for w in weeks if w["opponent_points"] is not None) / h2h_games, 1
                )
                if h2h_games
                else None,
                "weeks_counted": len(weeks),
            }
        )
        table.append(line)
    table.sort(key=lambda t: t["luck"], reverse=True)
    return table


def team_report(rows: list[dict], team: str, median_game: bool = False) -> dict:
    """Week-by-week detail for one team, with a summary of where the season went."""
    mine = [r for r in rows if r["team"] == team]
    if not mine:
        return {"error": f"No completed weeks found for '{team}'."}

    league_average = sum(r["points"] for r in rows) / len(rows)
    summary = next(t for t in luck_table(rows, median_game) if t["team"] == team)
    best = max(mine, key=lambda r: r["points"])
    worst = min(mine, key=lambda r: r["points"])

    # Weeks lost despite outscoring most of the league, and weeks won despite a poor score.
    half = lambda r: r["teams_that_week"] // 2  # noqa: E731
    unlucky_losses = [r["week"] for r in mine if _result(r) == "L" and r["rank_that_week"] <= half(r)]
    lucky_wins = [r["week"] for r in mine if _result(r) == "W" and r["rank_that_week"] > half(r)]

    return {
        "team": team,
        "summary": {
            **{k: v for k, v in summary.items() if k != "team"},
            "league_average_points_per_week": round(league_average, 1),
            "average_weekly_rank": round(sum(r["rank_that_week"] for r in mine) / len(mine), 1),
            "best_week": {"week": best["week"], "points": best["points"]},
            "worst_week": {"week": worst["week"], "points": worst["points"]},
            "weeks_lost_with_a_top_half_score": unlucky_losses,
            "weeks_won_with_a_bottom_half_score": lucky_wins,
            "bench_points_per_week": round(sum(r["bench_points"] for r in mine) / len(mine), 1),
        },
        "weeks": [
            {
                "week": r["week"],
                "points": r["points"],
                "rank_that_week": r["rank_that_week"],
                "opponent": r["opponent"],
                "opponent_points": r["opponent_points"],
                "result": _result(r),
                "median_result": "W" if r["beat_median"] else "L",
                "bench_points": r["bench_points"],
            }
            for r in mine
        ],
    }


def weekly_recap(rows: list[dict], week: int) -> dict:
    """The stories of one week: blowout, nail-biter, and who got robbed."""
    this_week = [r for r in rows if r["week"] == week]
    if not this_week:
        return {"error": f"Week {week} has no completed games."}

    # Each game appears twice (once per team); keep the winner's row.
    games = [r for r in this_week if _result(r) == "W"]
    margin = lambda r: round(r["points"] - r["opponent_points"], 2)  # noqa: E731
    losers = [r for r in this_week if _result(r) == "L"]
    winners = games

    def game(r: dict) -> dict:
        return {"winner": r["team"], "loser": r["opponent"], "score": f"{r['points']} - {r['opponent_points']}", "margin": margin(r)}

    recap = {
        "week": week,
        "highest_score": {"team": max(this_week, key=lambda r: r["points"])["team"], "points": max(r["points"] for r in this_week)},
        "lowest_score": {"team": min(this_week, key=lambda r: r["points"])["team"], "points": min(r["points"] for r in this_week)},
    }
    if games:
        recap["biggest_blowout"] = game(max(games, key=margin))
        recap["closest_game"] = game(min(games, key=margin))
    if losers:
        robbed = max(losers, key=lambda r: r["points"])
        recap["highest_score_that_lost"] = {"team": robbed["team"], "points": robbed["points"], "rank_that_week": robbed["rank_that_week"]}
    if winners:
        gifted = min(winners, key=lambda r: r["points"])
        recap["lowest_score_that_won"] = {"team": gifted["team"], "points": gifted["points"], "rank_that_week": gifted["rank_that_week"]}
    return recap
