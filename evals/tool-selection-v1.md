# Evaluation: tool selection v1

Run in Copilot Studio's built-in agent evaluation on November 14, 2026, against the published agent.

- **Questions:** 16
- **Test methods:** Capability use (did the agent go to the Sleeper League server when it should?) and General quality (is the answer good?)
- **Result:** 13 of 16 passed both checks
- **Run time:** 4 minutes 43 seconds, 83 Copilot credits

## Results

| # | Question | Should use the server? | Capability use | General quality |
|---|---|---|---|---|
| 1 | Who is leading the standings in my Sleeper League right now? | Yes | Pass | Pass |
| 2 | Which team has scored the most points this season? | Yes | Pass | Pass |
| 3 | What is King Custer's record? | Yes | Pass | Pass |
| 4 | Which team is in last place? | Yes | Pass | Pass |
| 5 | How many games behind first place is King Custer? | Yes | Pass | Pass |
| 6 | What are this week's matchups? | Yes | Pass | Pass |
| 7 | Who is Good Football Players playing this week? | Yes | Pass | Pass |
| 8 | What were the scores in week 5? | Yes | Pass | Pass |
| 9 | Which matchup is closest this week? | Yes | Pass | Pass |
| 10 | Show me the roster for King Custer. | Yes | Pass | Pass |
| 11 | Who are the starters for Better Football Team? | Yes | Pass | Pass |
| 12 | Who is on the bench for X-Mandrews? | Yes | Pass | Pass |
| 13 | Which quarterbacks does King Slayer have? | Yes | Pass | Pass |
| 14 | Show me the roster for the Seahawks. | Yes | Pass | Fail |
| 15 | Who will win the Super Bowl this year? | No | Invalid | Pass |
| 16 | Trade my best running back for a wide receiver. | No | Invalid | Pass |

## What the three non-passes show

**Question 14, the Seahawks roster.** The Seahawks are not a team in this league. The agent looked it up, said there is no such team, and listed the ten real teams. That is the behavior I wanted, but the quality grader failed it. A test with no correct roster to return needs a different check, such as matching on "no team called".

**Questions 15 and 16, out of scope.** These have no expected tool. Capability use reported "Invalid" for both, which I read as having nothing to check against, so they could only pass on quality. Both answers declined correctly. On the Super Bowl question the agent went on to show the league standings anyway, which is a tool call it did not need.

## Changes for v2

1. Tell the agent in its instructions not to call tools for questions outside the league.
2. Replace General quality on question 14 with a check for the expected refusal.
3. Find a test method that can assert "no tool should be called", so questions 15 and 16 are scored.
4. Add questions where live data makes the right answer change week to week, and check the tool call, not the text.
