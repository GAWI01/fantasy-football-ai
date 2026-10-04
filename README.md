# Fantasy Football AI

Fantasy Football AI (formerly FPL-AI) is a free, independent decision-support tool for Fantasy Premier League managers, combining live official data, prediction models, optimization and an explainable decision layer.

The repository now also contains a responsive premium web cockpit in `frontend/` and a resilient versioned API in `backend/`. See [docs/PREMIUM_DASHBOARD.md](docs/PREMIUM_DASHBOARD.md) for product surfaces, setup, deployment configuration and verification.

> **Status:** Free, non-commercial beta. Fantasy Football AI is not affiliated with or endorsed by the Premier League or Fantasy Premier League. Public operation follows the conditions in [the data-use release gate](docs/DATA_USE_RELEASE_GATE.md); paid or commercial use remains blocked.
> **Current product:** Responsive Next.js cockpit plus FastAPI decision API, public Team ID connection, live mode, interactive squad, five-GW Plan/What-if, player/fixture Explore and post-GW review.

Start with [the premium dashboard guide](docs/PREMIUM_DASHBOARD.md), inspect [the PRD status](docs/PRD_IMPLEMENTATION_STATUS.md), and follow the free-release conditions in [the data-use release gate](docs/DATA_USE_RELEASE_GATE.md).

## Run Fantasy Football AI locally

Fantasy Football AI consists of two processes:

- a FastAPI backend on `http://localhost:8000`
- a Next.js frontend on `http://localhost:3000`

The application reads public Fantasy Premier League data at runtime. You do not
need an FPL password or API key. To connect a team, use the numeric Team ID from
the official FPL URL, for example `https://fantasy.premierleague.com/entry/1234567/event/1`.

### Option A: Docker Compose (recommended)

Requirements:

- Git
- Docker Desktop with Docker Compose enabled

Clone and start the complete stack:

```powershell
git clone https://github.com/GAWI01/fantasy-football-ai.git
cd fantasy-football-ai
docker compose up --build
```

Open `http://localhost:3000`. The API health endpoint should return
`{"status":"ok"}` at `http://localhost:8000/health`.

Stop the stack with `Ctrl+C`, then run `docker compose down` if you also want to
remove the containers and network. Local source files and model artifacts are
not deleted.

### Option B: Run the development servers directly

Requirements:

- Python 3.12 or newer
- Node.js 22 or newer
- pnpm via Corepack
- Git

Clone the repository and prepare the backend from PowerShell:

```powershell
git clone https://github.com/GAWI01/fantasy-football-ai.git
cd fantasy-football-ai
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt -r backend/requirements.txt
python -m uvicorn backend.main:app --reload --port 8000
```

Leave that terminal running. In a second PowerShell terminal:

```powershell
cd fantasy-football-ai\frontend
corepack enable
pnpm install --frozen-lockfile
Copy-Item ..\.env.example .env.local
pnpm dev
```

Then open `http://localhost:3000`. Useful local checks are:

```powershell
Invoke-RestMethod http://localhost:8000/health
Invoke-RestMethod http://localhost:8000/api/v1/status
```

On macOS/Linux, activate the virtual environment with
`source .venv/bin/activate` and copy the frontend environment file with
`cp ../.env.example .env.local`.

### Local configuration

Only variable names are documented here; never commit real secrets in `.env`
files.

| Variable | Purpose | Local default |
| --- | --- | --- |
| `NEXT_PUBLIC_API_URL` | Browser-visible backend origin, compiled into the frontend | `http://127.0.0.1:8000` |
| `FPL_AI_CORS_ORIGINS` | Comma-separated frontend origins accepted by FastAPI | `http://localhost:3000,http://127.0.0.1:3000` |

The included `.env.example` contains safe local values. The frontend copy must
be named `frontend/.env.local`; it is ignored by Git.

### Troubleshooting

- **The page opens but data does not load:** verify `/health` and
  `/api/v1/status`, then confirm `frontend/.env.local` points to port `8000`.
- **CORS error in the browser:** include the exact frontend origin in
  `FPL_AI_CORS_ORIGINS` and restart the backend.
- **Team not found:** use the numeric public Team ID, not a team name or league
  ID. A team may be unavailable before its first official Gameweek deadline.
- **Stale dependencies:** rerun `pnpm install --frozen-lockfile` and the two
  Python `pip install` commands above.

For production-like local startup and hosted deployment checks, see
[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

## Vision

The end product should not merely answer “who are the 15 best players?”

It should answer:

> Given my current squad, budget, fixtures, expected minutes, player roles, risk, future schedule and available chips, what is the best FPL decision?

The system is deliberately split into two layers:

- **Python/model layer:** data collection, feature engineering, predictions, xMins, optimization, constraints and structured outputs.
- **AI/ChatGPT layer:** interpretation, context, explanation, challenge of model results, transfer/captain/chip discussion.

**Model = calculation and search. AI = interpretation, context and decision support.**

## What already exists

The project has successfully built:

- current FPL player-data ingestion
- GW1 historical live-data retrieval
- GW2 player predictions
- availability features
- xMins/start probability features
- rotation-risk features
- initial squad/Wildcard optimizer experiments

The served forecast is GW6/2026-27 (`gw6_predictions_v12.csv`, 667 players)
from the certified model `models/fpl_model_v3.pkl`, retrained on 2020-21 to
2025-26 and tested on the current season's completed Gameweeks.
`python -m historical_data.refresh_predictions` publishes each next Gameweek
once the previous one has final scores.
See [docs/MODEL_PIPELINE.md](docs/MODEL_PIPELINE.md) for the features,
validation evidence, limitations and commands. The earlier GW6 v11 and GW3
artifacts remain archived and unverified.

## V1–V5: what we learned

V1–V5 are **development versions, not different Wildcards**.

All versions attempted variants of brute-force candidate generation and positional combination. They became too slow because the search space exploded.

Typical progression:

- V1: ~140 optimizer candidates; pandas/DataFrame operations became the bottleneck.
- V2: stronger availability/xMins filtering, but combination search remained slow.
- V3: positional combinations such as 45 GKP, 1,000 DEF, 1,000 MID, 816 FWD; combining groups remained expensive.
- V4: more aggressive filtering; still too slow during cross-position combination.
- V5: 97 active candidates, with 66 GKP / 8,000 DEF / 8,000 MID / 1,140 FWD combinations; still reached hundreds of thousands of partial DEF combinations and stalled during group combination.

**Conclusion:** Do not keep patching brute-force. Change the optimization method.

## Current principle

> **Do not optimize for maximum complexity. Optimize for maximum useful signal per unit of computation.**

The target is a model that captures important FPL mechanics while running in seconds rather than several minutes.

## Planned pipeline

FPL API → current data → historical data → features → availability/xMins → predictions → fixtures/context → squad/transfer/chip optimizer → weekly report → AI analysis.

## Major planned capabilities

### Optimizer
- MILP/ILP or another exact/efficient constraint solver
- 15-player squad
- 2 GKP / 5 DEF / 5 MID / 3 FWD
- budget constraint
- max 3 players per club
- valid starting XI and bench
- captain/vice-captain
- normal-transfer mode
- Wildcard mode
- Free Hit mode
- Bench Boost mode
- multi-GW objective
- optional risk/differential mode

### Player point routes

The optimizer must understand *why* players score, not treat same-position players as interchangeable.

**DEF**
- clean sheets
- goals
- assists
- bonus
- defensive contribution / DefCon
- set pieces
- attacking positioning
- crosses/key passes
- expected minutes

**MID**
- goals/xG
- assists/xA
- shots
- chances created/key passes
- set pieces
- penalties
- bonus
- clean-sheet potential
- defensive contribution where relevant
- role and expected minutes

**FWD**
- goals/xG
- shots/shots in box
- big chances
- assists/xA
- penalties
- bonus
- expected minutes
- fixture context

**GKP**
- clean-sheet probability
- saves
- goals conceded
- bonus
- penalty-save potential
- expected minutes
- value

Useful archetypes include offensive full-backs, defensive-action monsters, set-piece centre-backs, clean-sheet defenders, elite attackers, creators, talismans and value picks.

### xMins / availability
The current implementation has availability, xMins, start probability and rotation-risk features, but the current xMins logic is not considered final.

Future target: a proper minutes model using recent minutes, starts, rotation patterns, injury status, squad context and fixture congestion.

### Uncertainty and ownership
Add:
- prediction uncertainty / variance
- ownership
- Effective Ownership where useful
- safe vs aggressive optimization modes
- captaincy risk/reward
- differential strategy

### Multi-Gameweek planning
Wildcard should not automatically maximize only one Gameweek.

Use a short horizon such as GW+1 through GW+5 with decreasing weights, then validate the weighting historically.

### Chip strategy
The system should decide **whether a chip should be used**, not just generate a chip team.

Compare:
- use Wildcard now
- keep Wildcard and use normal transfers
- save for a better future opportunity
- other available chip strategies

### Fixtures/context
Prefer stronger underlying team-strength/context signals over relying only on coarse FDR.

Potential inputs:
- xG scored/conceded
- home/away splits
- fixture run
- clean-sheet probability
- attacking environment
- rotation/congestion

### Backtesting
Before trusting the system, validate:
- predicted vs actual player points
- predicted vs actual minutes
- optimizer decisions vs actual Gameweeks
- value models
- captain model
- transfer strategy
- chip strategy

## Automation goal

Eventually one weekly runner should perform the pipeline automatically. The user should not need to open and run many scripts manually every Gameweek.

## GitHub goal

The repository should be clean and understandable.

Keep V1–V5 as historical reference under `legacy/` or git history rather than as competing current scripts.

Include:
- README
- architecture documentation
- setup/dependencies
- tests
- current pipeline
- legacy versions
- example outputs
- clear data/privacy notes

## Important implementation rule

Do not start by writing another giant optimizer script.

First inspect the current codebase, identify reusable components, define clean data contracts, then implement the new optimizer as a separate, testable module.
