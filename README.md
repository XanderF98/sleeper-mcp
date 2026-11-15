# Sleeper League MCP Server

## How it works

```
Copilot Studio agent  --MCP (Streamable HTTP)-->  this server (hosted on Render)  --HTTPS-->  Sleeper public API
```

1. A user asks the agent a question, such as "Who's in first place in my league?"
2. The agent reads each tool's description and decides which tool answers the question.
3. The agent calls that tool on this server over MCP.
4. The server fetches live data from Sleeper's public API, shapes it into a compact answer, and returns it.
5. The agent writes the reply from the returned data.

## Tools

| Tool | What it returns |
|---|---|
| `get_standings` | Every team's wins, losses, ties, points for and points against, best record first |
| `get_matchups` | Head-to-head matchups and scores for a week (defaults to the current NFL week) |
| `get_roster` | One team's starters and bench, with player names, positions and NFL teams |
| `get_luck_report` | Which teams the schedule has helped or hurt, luckiest first |
| `get_team_report` | One team's season week by week, with where it ranked each week and how lucky it has been |
| `get_weekly_recap` | One week's stories: biggest blowout, closest game, the highest score that still lost |

The description on each tool matters as much as the code. It is the only thing the agent sees when it decides whether to call the tool.

## Luck analysis

Standings say who is winning. They don't say who deserves to be. Your record depends on who you happened to play each week, and your score doesn't, so the luck tools compare every team's score against the whole league every week.

- **All-play record:** how a team would have done playing every other team each week.
- **Expected wins:** each week, the share of the league a team outscored, added up over the season.
- **Luck:** real head-to-head wins minus expected wins. Positive means the schedule helped. Negative means it hurt.

My league also plays the league median every week, so each team gets two results: one against its opponent and one for finishing in the top half. The median result depends only on your own score, so it's reported separately and kept out of the luck number.

The maths lives in `luck.py` as plain functions, and `tests/test_luck.py` checks it against a made-up four-team league with hand-calculated answers.

## Design choices

- **Read-only.** The server only reads public league data. It cannot change lineups or make trades.
- **Small, shaped responses.** Sleeper's raw responses are large and keyed by internal IDs. Each tool returns only what an agent needs, with team and player names resolved, so the agent uses fewer tokens and makes fewer mistakes.
- **Caching.** League data is cached for 60 seconds and the full player list for a day, so repeated questions don't hammer Sleeper's API.
- **Stateless HTTP.** The server keeps no per-session state, which suits a free hosting tier that sleeps when idle.

## Run it locally

Requires Python 3.10 or newer.

```
pip install -r requirements.txt
python server.py
```

The MCP endpoint is `http://localhost:8000/mcp`.

To point it at a different league, set the `SLEEPER_LEAGUE_ID` environment variable. Set `SLEEPER_USERNAME` to your Sleeper username so questions about "my team" work.

## Deploy

The server runs as a single web service. On Render:

- Build command: `pip install -r requirements.txt`
- Start command: `python server.py`

The host supplies the port through the `PORT` environment variable.

## Connect it to a Copilot Studio agent

1. In the agent, add a tool and choose Model Context Protocol.
2. Enter the server's public URL ending in `/mcp`. Choose no authentication for an open server, or OAuth 2.0 for a protected one (see Authentication below).
3. Create the connection and add it to the agent. The tools appear with their descriptions.
4. Ask the agent a league question in the test chat and confirm it reports using a tool.

## Authentication

The server can run open or behind OAuth 2.0 with Microsoft Entra ID as the sign-in service. Setting three environment variables turns the lock on:

| Variable | What it is |
|---|---|
| `ENTRA_TENANT_ID` | The organization's directory ID |
| `ENTRA_API_CLIENT_ID` | The client ID of the server's own app registration |
| `PUBLIC_URL` | The server's public address, without `/mcp` |

With the lock on, every call must carry an access token, and `auth.py` checks four things before the server answers:

1. **Signature:** the token was signed by Entra ID, using its published keys.
2. **Issuer:** it came from this organization, not another one.
3. **Audience:** it was issued for this server, not some other API.
4. **Expiry:** it has not run out.

The token must also carry the `league.read` scope. A call with no token gets a 401 response, and a valid token without the scope gets a 403.

### How the pieces fit

```
Copilot Studio  --1. sends the user to sign in-->  Entra ID
Copilot Studio  <--2. receives an access token--   Entra ID
Copilot Studio  --3. calls the server with the token-->  this server
this server     --4. checks the token against Entra's public keys, then answers
```

Setting it up took two app registrations in Entra ID:

- **One for the server.** It exposes the `league.read` scope. It has no secret, because the server only verifies tokens and never requests them.
- **One for Copilot Studio as the client.** It has a client secret, permission to request `league.read`, and Copilot Studio's callback address as its redirect URI.

In Copilot Studio the tool's connection uses OAuth 2.0 with manual settings: the client ID and secret, Entra's authorize and token addresses for the tenant, and the scope `api://<server client ID>/league.read`.

### How I tested it

- `tests/test_auth.py` covers nine cases with locally signed tokens: valid tokens in both of Entra's formats are accepted; a missing token, wrong audience, another tenant's token, an expired token, a forged signature and a garbage string are all refused; a token without the scope gets a 403. Run them with `pip install pytest && pytest`.
- End to end on November 14, 2026: opening the server's address in a browser returned `invalid_token`, and the agent, signed in through Entra ID, answered a standings question with `200 OK` in the server log.

## Evaluation

I test the agent with a fixed set of 16 questions in Copilot Studio's built-in evaluation: 13 that need the server, one about a team that doesn't exist, and two the agent should decline.

| Run | Passed both checks | Notes |
|---|---|---|
| Tool selection v1, November 14, 2026 | 13 of 16 | All 13 lookup questions passed. The three others exposed gaps in the test design and one unneeded tool call. |

The questions, the per-question results, and what I'm changing for the next run are in [evals/tool-selection-v1.md](evals/tool-selection-v1.md).

## What went wrong along the way

Two things stopped me before the agent answered its first question, and none of them were in the code.

- **Copilot Studio wouldn't create an agent.** A brand-new Microsoft 365 organization has no Dataverse database, and agents are stored there. As the admin I had to add Dataverse to the default environment in the Power Platform admin center.
- **The first test message failed with "You need credits to continue."** The MCP connection was fine and the three tools had loaded. The environment just had zero Copilot credits. Activating the Copilot Studio trial from the admin center's Marketplace fixed it, a few minutes after checkout.

The setup around the agent took longer than the server did.

## Limitations and next steps

- **No per-user permissions.** OAuth controls who can call the server, but every signed-in user sees the same league. There is one scope, `league.read`.
- **One league.** The league ID is set by configuration, not chosen per user.
- **No waiver or trade data yet.** Trending players and waiver-wire activity are natural additions.
- **Luck covers scores only.** It doesn't judge lineup decisions, such as points left on the bench in the wrong slot.

## A note on how this was built

I built this as a learning project, with Claude as a coding assistant for the server code. I deployed it, connected it to Copilot Studio, and tested it myself.
