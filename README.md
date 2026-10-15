<div align="center">

<img src="frontend/public/icons/icon-192.png" alt="FF.AI app icon" width="96">

# Fantasy Football AI

**Gameweek intelligence for Fantasy Premier League.**<br>
Transfers, captaincy, chips, live points and mini-leagues. One clear plan per deadline.

[**Open the app →**](https://fantasyfootball-ai.vercel.app)

[![Refresh predictions](https://github.com/GAWI01/fantasy-football-ai/actions/workflows/refresh-predictions.yml/badge.svg)](https://github.com/GAWI01/fantasy-football-ai/actions/workflows/refresh-predictions.yml)

</div>

![Home: this Gameweek's to-do with the transfer, captain, chips and the main injury risk](docs/screenshots/overview.webp)

## What you get

Enter your public FPL Team ID. No login is needed, and the app never changes
your team.

| Feature | What it does |
|---|---|
| ✅ **Gameweek to-do** | Home opens with this week's list: the transfer (or roll), the captain, the chip call and the player to check, with a confidence level. The plan is ready as soon as the previous deadline passes. |
| 📡 **Live** | Live points against the model's expectation. Tap any player for their points breakdown. |
| 🔁 **Transfers** | Every option compared on one scale, a two-week plan (move now or wait?) and **Try your own swap**: is your idea better than the plan? |
| 👑 **Captain** | A realistic points range for each candidate, and a pick that weighs safe against differential for your mini-league position. |
| 🃏 **Chips** | Play now or save, a season chip plan around blank and double Gameweeks, and the best Free Hit and Wildcard squads right now. |
| 🏆 **Mini-leagues** | The race, a head-to-head against any rival, and the players your league relies on. |
| 💷 **Prices** | Who is likely to rise or drop tonight, and price-smart swaps that do so without losing points. |
| 📊 **Explore & History** | Every player's forecast, xG and xA per 90, fixture runs with clean-sheet odds, and a season review against the model. |
| 📱 **Install** | Add it to your Home Screen and it opens like an app. |

<table>
  <tr>
    <td width="50%"><img src="docs/screenshots/plan.webp" alt="Plan, Transfers tab: Ajayi out, Gvardiol in, with the expected gain"></td>
    <td width="50%"><img src="docs/screenshots/plan-captain.webp" alt="Captain against your league: each candidate's points range and whether rivals captain him"></td>
  </tr>
  <tr>
    <td align="center"><b>Transfers</b>: the move and why</td>
    <td align="center"><b>Captain</b>: safe or differential, for your league</td>
  </tr>
  <tr>
    <td><img src="docs/screenshots/league.webp" alt="Mini-league race and a head-to-head against the manager above you"></td>
    <td><img src="docs/screenshots/prices.webp" alt="Price changes: countdown to the next change and a price-smart swap"></td>
  </tr>
  <tr>
    <td align="center"><b>Mini-leagues</b>: the race and your rival</td>
    <td align="center"><b>Prices</b>: tonight's risers and fallers</td>
  </tr>
</table>

<sub>Rival team names and the league name in these screenshots are anonymised.</sub>

**[See every feature with screenshots →](docs/FEATURES.md)**

## How it works

```mermaid
flowchart LR
    FPL[Official FPL API] --> API[FastAPI backend]
    CSV[Published forecast] --> API
    API --> ENG[Decision engine]
    ENG --> API
    API --> WEB[Next.js app]
    GHA[GitHub Actions<br/>every 30 minutes] --> CSV
```

- **Forecast:** a gradient-boosting model of each player's points. In the
  inspected 2026/27 GW1–5 evaluation its mean absolute error was 1.26, against
  1.35 for a last-five average. It is re-checked after every Gameweek; future
  improvements require evaluation on previously reserved rounds.
- **Decisions:** one optimiser picks the squad, XI and captain over five
  weighted Gameweeks. Holding, free transfers and hits are scored on one
  scale.
- **Honest labels:** every number's source (FPL data, Model or Derived) is
  labelled, once per card, and uncertainty is shown, never hidden.

More detail: [architecture](docs/ARCHITECTURE.md) ·
[model](docs/MODEL_PIPELINE.md) · [API](docs/API.md)

## Run it locally

```bash
git clone https://github.com/GAWI01/fantasy-football-ai.git
cd fantasy-football-ai
docker compose up --build        # app on :3000, API on :8000
```

<details>
<summary>Without Docker (Python 3.12+, Node.js 22+)</summary>

```bash
python -m venv .venv && source .venv/bin/activate
python -m pip install -r requirements.txt -r backend/requirements.txt
python -m uvicorn backend.main:app --reload --port 8000
```

In a second terminal:

```bash
cd frontend
corepack enable && pnpm install --frozen-lockfile
cp ../.env.example .env.local
pnpm dev
```

| Variable | Purpose | Default |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | Backend origin, compiled into the app | `http://127.0.0.1:8000` |
| `FPL_AI_CORS_ORIGINS` | App origins the API accepts | `http://localhost:3000,http://127.0.0.1:3000` |

</details>

<details>
<summary>Tests</summary>

```bash
python -m pytest                 # backend, decision engine, model pipeline
python -m benchmark.run          # decision benchmark on recorded real teams
cd frontend && pnpm test && pnpm lint && pnpm exec tsc --noEmit
```

</details>

## Docs

| Doc | What's inside |
|---|---|
| [Features](docs/FEATURES.md) | Every page and what each number means |
| [Architecture](docs/ARCHITECTURE.md) | Backend, decision engine, forecasts, repository map |
| [Model](docs/MODEL_PIPELINE.md) | Training, certification and limitations |
| [Decision engine contract](docs/DECISION_ENGINE_CONTRACT.md) | The interface the decision engine is built to: inputs, outputs and guarantees |
| [Deadline snapshots](docs/DEADLINE_SNAPSHOTS.md) | The archive of public data captured before each deadline |
| [API](docs/API.md) | Every endpoint |
| [Deployment](docs/DEPLOYMENT.md) | Railway and Vercel; merging to `master` deploys |
| [App icon](docs/APP_ICON.md) | How to swap the icon |
| [Data sources](docs/DATA_SOURCES.md) | Where the data comes from, the conditions and personal data |
| [Data notice](DATA_NOTICE.md) | Who owns the data, and how to ask for removal |
| [Privacy and terms](https://fantasyfootball-ai.vercel.app/privacy) | The public privacy notice and terms of use |
| [Contributing](.github/CONTRIBUTING.md) | How to propose a change, and the data and privacy rules |
| [Security](.github/SECURITY.md) | How to report a vulnerability privately |

## Data and credits

- **Historical data:** the model is trained on past FPL seasons from
  [**vaastav/Fantasy-Premier-League**](https://github.com/vaastav/Fantasy-Premier-League)
  by Vaastav Anand, used with his permission and this attribution. Thank you!
- **Live data:** the public Fantasy Premier League API.

---

<sub>Free, independent and non-commercial. Not affiliated with or endorsed by
the Premier League, Fantasy Premier League or any football club. FPL data,
club names, colours and marks belong to their owners; kits are simplified
drawings made for this site. Code under the [MIT licence](LICENSE); data is not covered,
see [DATA_NOTICE.md](DATA_NOTICE.md). Made by [GAWI01](https://github.com/GAWI01).</sub>
