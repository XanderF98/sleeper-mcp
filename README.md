# Sleeper League MCP Server

A small Model Context Protocol (MCP) server that gives an AI agent read-only access to a Sleeper fantasy football league. I built it to learn how MCP servers plug into Microsoft Copilot Studio agents, end to end: write the tools, host the server, connect an agent, and test it.

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

The description on each tool matters as much as the code. It is the only thing the agent sees when it decides whether to call the tool.

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

To point it at a different league, set the `SLEEPER_LEAGUE_ID` environment variable.

## Deploy

The server runs as a single web service. On Render:

- Build command: `pip install -r requirements.txt`
- Start command: `python server.py`

The host supplies the port through the `PORT` environment variable.

## Connect it to a Copilot Studio agent

1. In the agent, add a tool and choose Model Context Protocol.
2. Enter the server's public URL ending in `/mcp`, with no authentication.
3. Create the connection and add it to the agent. The three tools appear with their descriptions.
4. Ask the agent a league question in the test chat and confirm it reports using a tool.

## Evaluation

I test the agent with a fixed set of 16 questions in Copilot Studio's built-in evaluation: 13 that need the server, one about a team that doesn't exist, and two the agent should decline.

| Run | Passed both checks | Notes |
|---|---|---|
| Tool selection v1, November 14, 2026 | 13 of 16 | All 13 lookup questions passed. The three others exposed gaps in the test design and one unneeded tool call. |

The questions, the per-question results, and what I'm changing for the next run are in [evals/tool-selection-v1.md](evals/tool-selection-v1.md).

## Limitations and next steps

- **No authentication yet.** Anyone with the URL can call the server. That is acceptable for public, read-only data, and the next step is to put OAuth in front of it.
- **One league.** The league ID is set by configuration, not chosen per user.
- **Three tools.** Trending players and waiver-wire activity are natural additions.

## A note on how this was built

I built this as a learning project, with Claude as a coding assistant for the server code. I deployed it, connected it to Copilot Studio, and tested it myself.
