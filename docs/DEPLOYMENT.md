# Vercel + Railway: private staging/demo

This runbook prepares the existing Next.js + FastAPI application for internal
staging. It is **not public-release approval**. Follow
[DATA_USE_RELEASE_GATE.md](DATA_USE_RELEASE_GATE.md): the owner's 2026-10-03
decision accepts a free, non-commercial public beta only under its stated
conditions; commercial use remains blocked. That decision is not a data licence.

## Access boundary

The application has no login or API authentication. A secret-looking URL and
CORS do not make a deployment private. Before enabling external access, put
both the frontend and API behind an organization-approved access boundary.
Verify that its browser fetch/CORS behavior works with the two origins; frontend
protection alone leaves the API open. Do not put an access token in
NEXT_PUBLIC_API_URL or any other NEXT_PUBLIC_* variable. If access protection
is not configured, do not expose either service as a public demo.

## Runtime artifact strategy

The backend image includes exactly these data files under
`historical_data/current_data/`:

- `players_current.csv`
- `players_raw.csv`
- `teams_current.csv`
- `fixtures_current.csv`
- `gameweeks_current.csv`
- `manifest.json`
- `gw6_predictions_v11.csv`
- `gw6_predictions_v11.csv.manifest.json`

The current manifest, its certified sidecar and the raw player snapshot were
already tracked. Five narrow .gitignore exceptions make the remaining serving
CSVs eligible for version control. Include these files in the staging commit;
review `git status` before committing. No blanket exception for generated data
is used. The root .dockerignore is an allowlist for backend serving code and
these files. Training histories, features, pickle models, SQLite, backups,
frontend files, tests, secrets and development environments are excluded.

The served forecast is named by `manifest.json` (currently
`gw6_predictions_v13.csv`, GW6/2026-27, 667 rows) and carries the certified
model's provenance, so `/api/v1/status` reports it as validated. Each next
Gameweek's forecast is produced by `python -m historical_data.refresh_predictions`
once the previous Gameweek is final; committing its output redeploys the image.
Older artifacts (GW3 v11, GW6 v11) remain archived and are reported as
unverified if ever selected. See docs/MODEL_PIPELINE.md.

The API needs predictions and local team/fixture context for decisions; legacy
player routes use the player snapshot. Raw players and gameweeks are included
for complete structural/relationship validation. Review uses the published
prediction sidecar and may honestly be unavailable for other Gameweeks.
`fpl.db`, training features and the model files in `models/` are not serving inputs.
No persistent database or volume is necessary for this immutable-image strategy.

The Docker build runs `python -m backend.runtime_artifacts` and imports the API.
Validation checks current tables, prediction columns, row count, finite numeric
values, IDs and matching manifest/sidecar metadata. It does not call FPL or claim
freshness. To publish a new forecast, run
`python -m historical_data.refresh_predictions`, commit its output and merge it
to `master`; Git and Docker already allow every versioned forecast and sidecar.
Older artifacts stay in place for Review. Never rewrite old certification
timestamps to manufacture pre-deadline evidence.

## Automatic deploys

Merging to `master` deploys both services; no CLI step is needed.

- Railway service `backend`: source `GAWI01/fantasy-football-ai`, branch
  `master` (reconnected 2026-10-04 after the repository rename from `FPL-AI`).
- Vercel project `fpl-ai-staging`: production branch `master`, no Ignored Build
  Step (it was `exit 0`, which cancelled every Git build). Other branches get
  preview deployments.

Manual fallback from the repository root: `railway up --service backend --ci`
and `vercel deploy --prod --yes`.

## Railway backend

- Source: this Git repository, root directory `/` (not `backend/`).
- Dockerfile: `Dockerfile.backend`.
- Build variable: `RAILWAY_DOCKERFILE_PATH=Dockerfile.backend`.
- Runtime: set `PORT=8000` and route the service to port 8000, or configure the
  target to match a Railway-provided PORT. The container binds `0.0.0.0:$PORT`.
- Start command: use the Dockerfile default; no dashboard override is needed.
- Runtime variable: `FPL_AI_CORS_ORIGINS=https://YOUR-STAGING-WEB.vercel.app`.
  Multiple exact origins are comma-separated; no wildcard, URL path or secret.
- Health-check path: `/health` (liveness only).
- Inspect `/api/v1/status` separately before accepting the demo.
- Enable HTTPS and confirm outbound access to official FPL endpoints from the
  selected region. No FPL API key or application secret is required.

`backend/runtime-requirements.txt` pins serving dependencies, including SciPy,
from the existing environment; it avoids installing training/UI/test tooling.
The root and backend requirements remain the existing development/test setup.
The image uses Python 3.12; local Windows checks may use a different Python
version, so a successful Linux container build remains a separate gate.

## Vercel frontend

- Framework preset: Next.js.
- Root directory: `frontend`.
- Node.js: 22.x (matches the frontend Dockerfile).
- Package manager: pnpm 11.25.0, declared in package.json. pnpm-lock.yaml is
  authoritative; the redundant npm lockfile has been removed.
- Install command: `pnpm install --frozen-lockfile` (enable Corepack if needed).
- Build command: `pnpm build`; output directory: framework default.
- Set `NEXT_PUBLIC_API_URL=https://YOUR-API.up.railway.app` in the environment
  being deployed (Preview or Production). Use the API origin, without `/api`.
- Use a stable staging alias where possible and add its exact origin to backend
  CORS. Each additional preview origin needs an explicit CORS entry.

The browser fetches FastAPI directly. This URL is compiled into JavaScript;
a variable change requires a rebuild. Without it the client uses same-origin
`/api/v1/...`, which needs a proxy not provided by this split-host setup.
Do not mistake Vercel's environment name "Production" for public-release
permission: a staging alias still needs private access protection.

## Deployment order

1. Configure the private access boundary and deploy the backend from repository
   root with the serving bundle and Railway variables above.
2. Verify liveness, status, artifact load and official upstream reachability.
   Investigate degraded state; an old GW3 model is not a current forecast.
3. Set frontend NEXT_PUBLIC_API_URL to the verified HTTPS backend origin.
4. Deploy frontend with the Vercel settings above.
5. Update backend CORS with the final frontend origin if needed and restart it.
6. Run the hosted smoke tests through the intended private access boundary.

## Health versus readiness

`GET /health` returns `{ "status": "ok" }` when the process responds.
`GET /api/v1/status` retains its HTTP 200 envelope and original fields, adding:

- `data.artifacts.loaded`, `files`, and `prediction_rows` on validation success;
- `data.model.generated_at`: original manifest timestamp;
- `data.model.target_event`: official next event, or current event if no next;
- `data.model.matches_target_event`: true/false, or null if unknown.

Inspect `data.service_state` and `errors`, not HTTP 200 alone. Missing/corrupt
artifacts, unknown/mismatched target GW and stale upstream fallback prevent
`ready`. If the upstream is unavailable, artifact checks still run. Matching a
GW does not establish optimal accuracy or the age of undated CSVs; review the
recorded timestamp and data publication process before a current-GW demo.

## Local development and production stack

Copy .env.example to frontend/.env.local for local browser API configuration.
Set backend variables in its process environment; Uvicorn does not automatically
load the root example file. Run the documented README commands unchanged.
The root PORT example is for the backend; Next dev/start defaults to port 3000.
For Compose, keep API port 8000 and set NEXT_PUBLIC_API_URL to a browser-reachable
origin at build time. Then run `docker compose up --build`.
The existing render.yaml remains an alternative two-service deployment.

## Verification before hosting

From repository root in the project Python environment:

```text
python -m pip check
python -m pytest tests backend/tests -q
python -m backend.data_loader
python -m backend.runtime_artifacts
```

From frontend:

```text
pnpm install --frozen-lockfile
pnpm test
pnpm lint
pnpm exec tsc --noEmit
pnpm build
```

On a Docker-enabled host, from repository root:

```text
docker compose config
docker compose build
```

Legacy model/Streamlit tests still need ignored research artifacts in the local
working tree. The deployment regression separately copies only allowed runtime
files to a temporary directory and imports/validates them. Run the artifact and
deployment tests in a clean checkout too. This does not replace a Docker build.

## Hosted smoke test

Substitute real private staging URLs and a valid public Team ID:

```powershell
Invoke-RestMethod https://YOUR-API/health
Invoke-RestMethod https://YOUR-API/api/v1/status
Invoke-RestMethod https://YOUR-API/api/v1/dashboard/YOUR_TEAM_ID
Invoke-RestMethod https://YOUR-API/api/v1/plan/YOUR_TEAM_ID
Invoke-RestMethod 'https://YOUR-API/api/v1/fixture-matrix?horizon=5'
Invoke-RestMethod 'https://YOUR-API/api/v1/players?limit=20'
Invoke-RestMethod https://YOUR-API/api/v1/review/YOUR_TEAM_ID
Invoke-WebRequest https://YOUR-WEB/
```

Confirm X-Request-ID, exact-origin CORS, no mixed content, browser network URLs,
all six primary pages and static assets. Check errors/model target rather than
accepting degraded model output as current. Check invalid IDs, stale upstream
behavior, touch/keyboard/mobile flows and local preference persistence. Record
hosted cold/warm latency. Check unauthenticated outsiders cannot reach either
service. Review may be unavailable without an appropriate certified artifact.

No push, hosting operation or rights clearance is implied by this runbook.
