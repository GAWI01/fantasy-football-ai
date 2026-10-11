# API

Back to the [README](../README.md).

All endpoints are read-only and use public FPL data. Each response is an
envelope: `{ data, meta, errors }`, where `meta` carries the source,
freshness and version.

| Endpoint | Returns |
|---|---|
| `GET /health` | `{"status":"ok"}` |
| `GET /api/v1/status` | Forecast and official Gameweek state, and whether they match |
| `GET /api/v1/dashboard/{team_id}` | Squad, decision, intelligence (captain, chips, chip outlook, horizon), live Gameweek and history |
| `GET /api/v1/plan/{team_id}` | The decision alone |
| `GET /api/v1/evaluate/{team_id}?sell=…&buy=…` | Your own transfers scored against holding and the recommendation |
| `GET /api/v1/leagues/{team_id}` | The manager's private classic leagues |
| `GET /api/v1/league/{league_id}?team_id=…` | Standings, gaps, effective ownership, threats and differentials |
| `GET /api/v1/league/{league_id}/rival/{rival_id}?team_id=…` | Head to head: shared and unique players, captains |
| `GET /api/v1/players` | Every player with official stats and the forecast |
| `GET /api/v1/fixtures`, `GET /api/v1/fixture-matrix` | Fixtures and fixture runs with difficulty |
| `GET /api/v1/review/{team_id}?event=…` | A finished Gameweek against its pre-deadline forecast |

Interactive documentation is at `http://localhost:8000/docs` when running
locally.
