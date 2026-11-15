"""A made-up four-team league with three played weeks and known answers.

Week 1:  A 100 beat B 90      C 120 beat D 80
Week 2:  C 110 beat A 95      B 70 beat D 60     (A loses with the 2nd-best score)
Week 3:  A 130 beat D 85      B 105 beat C 100
Week 4:  not played yet
"""

NAMES = {1: "Aces", 2: "Bandits", 3: "Comets", 4: "Dragons"}

USERS = [
    {"user_id": "u1", "display_name": "alice", "metadata": {"team_name": "Aces"}},
    {"user_id": "u2", "display_name": "bob", "metadata": {"team_name": "Bandits"}},
    {"user_id": "u3", "display_name": "cara", "metadata": {"team_name": "Comets"}},
    {"user_id": "u4", "display_name": "dev", "metadata": {"team_name": "Dragons"}},
]

ROSTERS = [
    {"roster_id": i, "owner_id": f"u{i}", "players": [], "starters": [], "settings": {}}
    for i in (1, 2, 3, 4)
]


def _entry(roster_id, matchup_id, points, **extra):
    return {"roster_id": roster_id, "matchup_id": matchup_id, "points": points, **extra}


MATCHUPS = {
    1: [
        _entry(1, 1, 100.0, starters=["p1"], players_points={"p1": 100.0, "p2": 12.5}),
        _entry(2, 1, 90.0),
        _entry(3, 2, 120.0),
        _entry(4, 2, 80.0),
    ],
    2: [_entry(1, 1, 95.0), _entry(3, 1, 110.0), _entry(2, 2, 70.0), _entry(4, 2, 60.0)],
    3: [_entry(1, 1, 130.0), _entry(4, 1, 85.0), _entry(2, 2, 105.0), _entry(3, 2, 100.0)],
    4: [_entry(1, 1, 0.0), _entry(2, 1, 0.0), _entry(3, 2, 0.0), _entry(4, 2, 0.0)],
}
