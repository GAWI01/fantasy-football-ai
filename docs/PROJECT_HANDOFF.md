# FPL-AI handoff

Updated: 2026-10-11
Branch: `fix/decision-correctness-phase1`, based on `master` at `5306fdc`.
Milestone: Phase 1 decision correctness after the 2026-10-11 practical audit
(`docs/audit/PRACTICAL_PRODUCT_AUDIT_2026-10-11.md`). Full report, root causes
and before/after benchmark: `docs/audit/PHASE1_DECISION_CORRECTNESS.md`.

## Mini-leagues (2026-10-11)

Branch `feature/mini-league` (on top of Phase 2). New page `/league` and API
`/api/v1/leagues/{team_id}`, `/api/v1/league/{league_id}?team_id=`,
`/api/v1/league/{league_id}/rival/{rival_id}?team_id=` (`backend/league_service.py`).
Private leagues only; squads from the latest deadline that has passed (FPL does
not publish next-deadline squads); top 30 managers analysed per league to stay
within the upstream request budget. Rivals' EO excludes you; threat = ≥50%
rival EO you do not own; differential = your starter under 25% rival EO.
VERIFIED: tests (pytest 535, frontend 113), lint/tsc/build; browser check on a
real 7-manager private league (desktop and 390 px).

## Phase 2 status (2026-10-11)

Branch `feature/decision-quality-phase2` (on top of Phase 1). See
`docs/audit/PHASE2_DECISION_QUALITY.md`.

DONE: derived selling prices; lineup, captain and bench from the squad after
the recommended transfers (owned-squad lineup kept for My Team); captain by
expected points with a 0.3-point tie band; decision cache; new "Test your own
move" (`/api/v1/evaluate/{team_id}`).
VERIFIED: pytest 531 passed, frontend 112 passed, lint/tsc/build clean;
benchmark 15/15 known selling prices, 0 sold captains or lineup players; live
browser check (GW6 live, provisional GW7).
NOT VERIFIED: derived selling prices against private FPL values; Docker/hosted.
REMAINING: multi-week planning, chip timing, mini-league/EO, team-news feed,
model calibration, policy backtest.

## Phase 1 status (2026-10-11)

DONE
- Next-GW planning during a live GW: provisional forecast for GW N+1 once GW N's
  deadline passes (history to N-1), final once N is data-checked; live points
  keep comparing against GW N's pre-deadline forecast; UI shows "Provisional".
- One canonical action planner (`optimizer/action_planner.py`): starting XI +
  captain per horizon GW, bench as autosub cover only, hold/roll, 1..FT free
  transfers and up to two hits on one scale, roll value for banked FTs.
- One transfer recommendation per response; intelligence explains, never re-ranks.
- 5-GW gain counted once; no extra minutes discount on model points.
- Gameweek-specific availability (`backend/availability.py`): return dates in
  official news, recovery assumptions, blanks do not zero later GWs.
- Action labels HOLD / SINGLE_TRANSFER / MULTI_TRANSFER / HIT (WILDCARD /
  FREE_HIT only when recommended); margin-vs-uncertainty confidence (or UNKNOWN);
  evidence-based chips; truthful UI copy (no threshold claim, hits real).
- Unknown Team ID: 404 JSON with CORS, no upstream retry.
- Recorded real-team decision benchmark (`benchmark/`, `python -m benchmark.run`).

VERIFIED
- `python -m pytest tests backend/tests`: 522 passed, 1 skipped.
- Frontend: `pnpm test` 109 passed, `pnpm lint`, `tsc --noEmit`, `pnpm build` clean.
- Benchmark on 12 recorded real teams (+ FT 0/2/3): 15/15 consistent plans,
  0 bench-goalkeeper transfers, 0 wrong MULTI labels, 0 automatic Wildcards.
- Real refresh pipeline (scratch copy, 2026-10-11, GW6 live) published a
  provisional GW7 forecast; the real API served a GW7 plan; browser check of
  overview and plan page on desktop and 390 px.

NOT VERIFIED
- Docker image build (no Docker locally); hosted deployment; the scheduled
  GitHub Action publishing a provisional forecast on `master`.
- Policy constants are documented assumptions, not backtested.

REMAINING (see the phase report): model calibration (minutes risk, compressed
range, ranking), per-GW forecasts, captain ceiling/double counting, post-transfer
XI display, derived selling prices, FT rule after WC/FH, decision caching and
latency, chip timing across GWs, earlier audit items (quota, legacy code).

---

# Earlier handoff (2026-10-04)

Branch: `fix/audit-corrections`, based on `master` at `13bf200`.
Milestone: four audited correction groups, then a retrained and certified model
with automatic Gameweek refresh; Next.js + FastAPI + CSV serving is preserved.

## Current audit corrections

1. Backend contracts: official minutes/form survive model enrichment; wrong target
   GW/season is rejected; fresh availability overlays decision inputs; review
   projections retain the selected captain/XI; double-GW live classification is
   based on all fixtures. Manager display uses surname only; player display uses
   official web-name/surname and never first-name fallback.
2. Transfer/chip calculations: complete-plan budget/club constraints use MILP;
   chip comparisons use the recommended owned XI/bench/captain (the lineup the
   plan shows, not the previous Gameweek's picks) and the manager's budget. Unknown
   selling prices remain explicitly estimated. Opening-GW and consecutive Free
   Hit restrictions are enforced.
3. Pipeline: one shared feature implementation for training, validation and
   live forecasts; safe publication; blank/double fixtures. The model was then
   retrained (now contract v4, gradient boosting), tested on 2026-27 GW1-5 and
   certified with causality and production-parity checks (docs/MODEL_PIPELINE.md).
4. Frontend/build: event-aligned projections, correct multipliers and missing
   coverage, resource refresh, team-scoped history/overrides and honest freshness.
   Frontend Docker no longer copies a nonexistent public directory.

The served artifact is `gw6_predictions_v13.csv` (GW6/2026-27, 667 rows) from
the certified `models/fpl_model_v4.pkl`; `/api/v1/status` reports it as
validated. `python -m historical_data.refresh_predictions` publishes each next
Gameweek after the previous one is final; no scheduler runs it yet. The v11 GW6 and GW3 artifacts are
archived and unverified. Docker is unavailable locally; the backend allowlist
is exercised by tests/test_deployment_artifacts.py, not by a container build.

The data-use gate was changed by the owner on 2026-10-03 to conditionally accept
a free non-commercial public beta as a known risk. Commercial release remains
blocked. These fixes do not change that decision or establish a data licence.

## Historical staging record (superseded where it conflicts with the audit above)

The sections below preserve the earlier staging implementation and verification
record. Their GW3 counts, branch and deployment state are historical.

## Architecture

Next.js 16.3.3 / React 19.2.8 / TypeScript frontend in `frontend/` calls the
FastAPI app `backend.main:app` directly from the browser. `NEXT_PUBLIC_API_URL`
is a frontend build-time origin; `FPL_AI_CORS_ORIGINS` is the backend's explicit
origin allowlist. Root Python decision/optimizer modules combine cached official
FPL reads with local CSV predictions. User preferences/Team ID/history remain
in browser localStorage. No login, database service or LLM key is required by
this serving path. Legacy Streamlit/SQLite and offline ML remain separate.

## What changed

- `.dockerignore`: backend context allowlist with explicit secret/cache denial.
- `.gitignore`: five specific serving CSV exceptions, no broad data inclusion.
- `Dockerfile.backend`: pinned serving requirements, build-time data/import
  validation, PORT-aware listener and health check; non-root runtime retained.
- `backend/runtime-requirements.txt`: installed serving versions pinned,
  including SciPy and transitive dependencies; no training/UI/test packages.
  Existing root/backend development requirements are intentionally unchanged.
- `backend/runtime_artifacts.py`: read-only, isolated-directory bundle validator.
- `backend/data_loader.py`: optional directory argument enables isolated checks
  while preserving all existing default call sites.
- `backend/main.py`, `backend/api_models.py`: additive status artifact-load,
  generated-at, official target and target-match fields; stale/mismatched or
  missing data prevents ready. `/health` remains process liveness.
- `frontend/package.json`: pnpm 11.25.0 and Node >=22 declared.
- `frontend/package-lock.json`: removed; pnpm-lock.yaml unchanged/authoritative.
- `tests/test_deployment_artifacts.py`: checks production provider rather than
  ignored backup; validates a serving-only copy and Git artifact eligibility.
- `tests/test_runtime_artifacts.py`, `tests/test_status_api.py`: missing/corrupt
  files, metadata mismatch, row count, target mismatch and stale/unknown upstream.
- `.env.example`, `docs/DEPLOYMENT.md`: safe variables and exact hosting order,
  private access boundary, artifact publication and smoke-test instructions.
- `docs/PRD_IMPLEMENTATION_STATUS.md`: dated staging evidence; original local
  verification record retained.

Frontend API/CORS behavior was already suitable and remains unchanged. No
application redesign, dependency upgrade, real credentials or URL hardcoding.

## Artifact strategy and exact files

All serving data stays in `historical_data/current_data/`:

1. `players_current.csv` — new Git inclusion.
2. `players_raw.csv` — already tracked.
3. `teams_current.csv` — new Git inclusion.
4. `fixtures_current.csv` — new Git inclusion.
5. `gameweeks_current.csv` — new Git inclusion.
6. `manifest.json` — already tracked, unchanged.
7. `gw3_predictions_v11.csv` — new Git inclusion.
8. `gw3_predictions_v11.csv.manifest.json` — already tracked, unchanged.

The manifest and sidecar agree, with 623 rows and original generation time
2026-08-31T18:12:10+02:00 for GW3/2026-27. No freshness was invented. The frozen
snapshot can support internal inspection but is not a current-GW forecast.
Training data/features/models and fpl.db are not packaged. Read-only serving
needs no persistent volume; new publications require an image rebuild.

## Deployment settings

Railway: repository root, `RAILWAY_DOCKERFILE_PATH=Dockerfile.backend`, PORT=8000
(or matching provider PORT/target), health `/health`, explicit frontend CORS.
Vercel: root `frontend`, Node 22.x, pnpm 11.25.0, frozen install, `pnpm build`,
HTTPS Railway origin in NEXT_PUBLIC_API_URL before build. Backend first, inspect
status, frontend second, finalize CORS, then hosted smoke tests.
See [docs/DEPLOYMENT.md](DEPLOYMENT.md) for full instructions.

## Checks actually run

Python commands used `.venv/Scripts/python.exe` (Python 3.13.15 on Windows):

- `python -m pip check`: passed, no broken requirements.
- `python -m pip install --dry-run -r backend/runtime-requirements.txt`: passed;
  all pins already installed locally (not evidence of a Linux installation).
- `python -m pytest tests backend/tests -q`: 361 passed, one existing pandas
  FutureWarning in app_team.py; final run 18.46 seconds.
- `python -m backend.data_loader`: passed.
- `python -m backend.runtime_artifacts`: passed, eight files/623 predictions.
- New targeted tests were first observed failing, then passed after implementation.

Frontend commands used Node 24.20.0 / pnpm 11.25.0 locally:

- `pnpm install --frozen-lockfile`: passed; unchanged dependency lock.
- `pnpm test`: 18 files, 87 tests passed.
- `pnpm lint`: passed.
- `pnpm exec tsc --noEmit`: passed.
- `pnpm build`: passed with NEXT_PUBLIC_API_URL=https://staging-api.example.invalid
  as a deliberately nonfunctional build-check value, not a deployment URL.
- Inspected standalone/server.js, route manifest and emitted JS containing the
  configured API origin. Local standalone HTTP smoke: `/`, `/team`, `/plan`,
  `/explore`, `/review`, `/settings` and a JS asset all returned 200.

`git diff --check`: passed. DATA_USE_RELEASE_GATE.md and pnpm-lock.yaml unchanged.
Docker executable is absent: `docker compose config` / `docker compose build`
were **not run**. No hosted service or real-device/browser interaction tested.
Legacy research tests still depend on ignored development artifacts; only the
serving-only regression demonstrates independence from those local files.

### Final pre-commit corrections — 2026-10-03

Removed four Docker parent-directory exceptions that admitted unwanted
descendants. Only file exceptions remain; Docker traverses ignored ancestors
when a descendant file exception applies. Added regressions for whole-directory
exceptions and an exact serving-data file set. These are configuration/import
checks, not an actual Docker image build.

Converted the invalid Windows-encoded dash bytes in this file and
docs/PRD_IMPLEMENTATION_STATUS.md to UTF-8 while preserving existing valid text.
A documentation encoding regression now reads both files strictly as UTF-8.

After the corrections, the targeted deployment/status/runtime-artifact suite
passed: 26 tests. The full Python/frontend suites and production build above
are earlier evidence and were not rerun for these config/test/document changes.
Docker remains unavailable; the frozen GW3/August 31 snapshot and data-use gate
remain unchanged. Intended files are staged for review; no commit, push or
deployment has been performed.

## Remaining gates and exact next action

The code is prepared for a private staging attempt, not certified as hosted-ready.
Next: review the staged diff and approve a commit, then run
`docker compose config` and `docker compose build` on a Docker-enabled host.
Verify the Linux/Python 3.12 and Node 22 containers, then configure private access
for BOTH services before any externally reachable deployment. The app has no
authentication; CORS or an obscure URL is not private access control.

Refresh/certify the model bundle offline before presenting current-GW advice;
otherwise accept and label the frozen GW3/degraded demo. Run hosted HTTPS, CORS,
upstream reachability, latency and device checks. No push/deploy is authorized
by this handoff alone.

**Public free beta and paid release remain blocked by the unchanged
[DATA_USE_RELEASE_GATE.md](DATA_USE_RELEASE_GATE.md).** No licensing
clearance, public-launch approval or permission evidence was created.
