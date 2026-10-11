# Premium Live Dashboard Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a responsive Intelligence Cockpit whose Overview, My Team, Plan, Explore, and Settings destinations use current official FPL data and clearly separated model outputs after connection by public Team ID.

**Architecture:** FastAPI composes existing team, live, fixture, prediction, and decision services into a versioned application contract with source/freshness metadata. Next.js consumes that contract through one typed client, a shared team session provider, and focused route components; numerical prediction and optimization remain in Python.

**Tech Stack:** Python 3, FastAPI, requests, pandas, PuLP, pytest; Next.js 16.3.3, React 19.2.8, TypeScript 5.9, Tailwind CSS 4, Lucide React, Vitest, Testing Library.

**Spec:** `docs/superpowers/specs/2026-08-31-premium-live-saas-dashboard-design.md`

## Global Constraints

- Connect by public numeric FPL Team ID; do not request or store FPL credentials.
- Label important values as Live, Official, Model, or Derived.
- Keep prediction and optimization logic in Python; the frontend only presents structured results.
- Preserve existing API endpoints while adding `/api/v1` application endpoints.
- Retain Next.js 16.3.3 and React 19.2.8 and follow the checked-in Next.js documentation under `frontend/node_modules/next/dist/docs/`.
- Support useful degraded states when official, prediction, or decision data is unavailable.
- Support keyboard operation, visible focus, reduced motion, and layouts from 320 px through wide desktop.
- Treat current prediction artifacts as versioned model inputs, not live official data.

---

## File Structure

### Backend

- `backend/api_contract.py` — versioned response envelope and freshness metadata.
- `backend/fpl_gateway.py` — shared official-FPL HTTP, TTL cache, stale fallback, and request coalescing.
- `backend/dashboard_service.py` — composes independent domain results into the dashboard payload.
- `backend/data_manifest.py` — validates and reads the current prediction publication manifest.
- `backend/main.py` — mounts `/api/v1/status`, `/api/v1/dashboard/{team_id}`, and explorer routes while retaining legacy endpoints.
- Existing `backend/team_service.py`, `live_service.py`, and `fixture_service.py` keep their normalization responsibilities and delegate HTTP reads to the gateway.

### Frontend

- `frontend/lib/contracts.ts` — application-domain TypeScript contracts.
- `frontend/lib/api.ts` — the only browser-facing API client.
- `frontend/app/providers/TeamProvider.tsx` — local Team ID session, refresh, and connection lifecycle.
- `frontend/components/shell/AppShell.tsx` — desktop rail, mobile navigation, gameweek bar, and freshness state.
- `frontend/components/dashboard/OverviewDashboard.tsx` — decision hierarchy for the Overview route.
- `frontend/components/team/TeamPitch.tsx` — accessible team/bench presentation.
- `frontend/components/plan/PlanWorkspace.tsx` — transfer, captain, and horizon outputs.
- `frontend/components/explore/ExploreWorkspace.tsx` — live player and fixture exploration.
- `frontend/components/states/DataState.tsx` — loading, empty, stale, degraded, and unavailable states.
- `frontend/app/page.tsx`, `app/team/page.tsx`, `app/plan/page.tsx`, `app/explore/page.tsx`, and `app/settings/page.tsx` — thin route entry points.
- `frontend/app/globals.css` — responsive visual tokens and component layout.

---

### Task 1: Versioned API Envelope

**Files:**
- Create: `backend/api_contract.py`
- Create: `tests/test_api_contract_v1.py`

**Interfaces:**
- Consumes: timezone-aware `datetime` values and normalized domain dictionaries.
- Produces: `source_meta(source, fetched_at, stale=False, version=None) -> dict` and `api_envelope(data, meta, errors=()) -> dict`.

- [ ] **Step 1: Write failing contract tests**

```python
from datetime import datetime, timezone

from backend.api_contract import api_envelope, source_meta


def test_source_meta_serializes_utc_and_source_class():
    meta = source_meta("official", datetime(2026, 8, 31, 18, tzinfo=timezone.utc))
    assert meta == {
        "source": "official",
        "fetched_at": "2026-08-31T18:00:00+00:00",
        "stale": False,
        "version": None,
    }


def test_api_envelope_keeps_partial_errors():
    payload = api_envelope({"team": {"team_id": 7}}, {"event": 2}, [
        {"area": "prediction", "message": "Prediction unavailable"}
    ])
    assert payload["data"]["team"]["team_id"] == 7
    assert payload["meta"]["event"] == 2
    assert payload["errors"][0]["area"] == "prediction"
```

- [ ] **Step 2: Run the tests and confirm the missing module failure**

Run: `python -m pytest tests/test_api_contract_v1.py -q`

Expected: FAIL because `backend.api_contract` does not exist.

- [ ] **Step 3: Implement the envelope primitives**

```python
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable

SOURCE_CLASSES = frozenset({"live", "official", "model", "derived"})


def source_meta(source: str, fetched_at: datetime, *, stale: bool = False, version: str | None = None) -> dict[str, Any]:
    if source not in SOURCE_CLASSES:
        raise ValueError(f"Unsupported source class: {source}")
    if fetched_at.tzinfo is None:
        raise ValueError("fetched_at must be timezone-aware")
    return {
        "source": source,
        "fetched_at": fetched_at.astimezone(timezone.utc).isoformat(),
        "stale": stale,
        "version": version,
    }


def api_envelope(data: Any, meta: dict[str, Any], errors: Iterable[dict[str, str]] = ()) -> dict[str, Any]:
    return {"data": data, "meta": meta, "errors": list(errors)}
```

- [ ] **Step 4: Run the contract tests**

Run: `python -m pytest tests/test_api_contract_v1.py -q`

Expected: 2 passed.

- [ ] **Step 5: Commit the task**

```bash
git add backend/api_contract.py tests/test_api_contract_v1.py
git commit -m "feat: add versioned API response contract"
```

### Task 2: Cached Official FPL Gateway

**Files:**
- Create: `backend/fpl_gateway.py`
- Create: `tests/test_fpl_gateway.py`
- Modify: `backend/live_service.py`
- Modify: `backend/team_service.py`
- Modify: `backend/fixture_service.py`

**Interfaces:**
- Consumes: relative official FPL API paths and a monotonic clock.
- Produces: `FplGateway.get_json(path, ttl_seconds) -> GatewayResult`, where `GatewayResult` contains `data`, `fetched_at`, and `stale`.

- [ ] **Step 1: Write gateway cache and stale-fallback tests**

```python
from backend.fpl_gateway import FplGateway


class Response:
    status_code = 200
    def raise_for_status(self): pass
    def json(self): return {"events": [{"id": 2}]}


def test_gateway_coalesces_fresh_reads():
    calls = []
    gateway = FplGateway(http_get=lambda *a, **k: calls.append(a[0]) or Response(), clock=lambda: 100.0)
    first = gateway.get_json("bootstrap-static/", ttl_seconds=300)
    second = gateway.get_json("bootstrap-static/", ttl_seconds=300)
    assert first.data == second.data
    assert calls == ["https://fantasy.premierleague.com/api/bootstrap-static/"]


def test_gateway_returns_last_good_value_as_stale_after_network_error():
    state = {"fail": False}
    def get(*args, **kwargs):
        if state["fail"]: raise OSError("offline")
        return Response()
    now = {"value": 100.0}
    gateway = FplGateway(http_get=get, clock=lambda: now["value"])
    gateway.get_json("bootstrap-static/", ttl_seconds=1)
    state["fail"] = True
    now["value"] = 102.0
    assert gateway.get_json("bootstrap-static/", ttl_seconds=1).stale is True
```

- [ ] **Step 2: Run the focused tests and confirm failure**

Run: `python -m pytest tests/test_fpl_gateway.py -q`

Expected: FAIL because `FplGateway` is undefined.

- [ ] **Step 3: Implement gateway with a locked per-path cache**

Implement a `GatewayResult` frozen dataclass and `FplGateway`. Use `threading.RLock`, `requests.get`, a ten-second timeout, FPL-AI user agent, an in-memory dictionary keyed by normalized path, and the last successful response as a stale fallback. Reject non-dictionary/list JSON. Convert `requests.RequestException`, `OSError`, invalid JSON, and HTTP failures into `FplGatewayError` only when no cached success exists.

```python
@dataclass(frozen=True)
class GatewayResult:
    data: Any
    fetched_at: datetime
    stale: bool
```

- [ ] **Step 4: Delegate existing service `_get_json` wrappers to the shared gateway**

Keep the wrappers so current monkeypatch-based tests remain stable. Each wrapper calls `default_gateway.get_json(...)` and returns `.data`; use 300 seconds for bootstrap, 900 for fixtures, 60 for manager data, and 45 for active event live data.

- [ ] **Step 5: Run gateway and existing service tests**

Run: `python -m pytest tests/test_fpl_gateway.py backend/tests/test_live_service.py backend/tests/test_fixture_service.py tests/test_team_service.py -q`

Expected: all pass.

- [ ] **Step 6: Commit the task**

```bash
git add backend/fpl_gateway.py backend/live_service.py backend/team_service.py backend/fixture_service.py tests/test_fpl_gateway.py
git commit -m "feat: centralize cached FPL API access"
```

### Task 3: Resilient Dashboard Composition

**Files:**
- Create: `backend/dashboard_service.py`
- Create: `tests/test_dashboard_service.py`
- Modify: `backend/main.py`
- Modify: `tests/test_decision_api.py`

**Interfaces:**
- Consumes: `team_id: int` and existing domain callables for team, live players, history, fixtures, predictions, and decision output.
- Produces: `build_dashboard(team_id, dependencies=None) -> dict` and `GET /api/v1/dashboard/{team_id}`.

- [ ] **Step 1: Write a partial-success dashboard test**

```python
from backend.dashboard_service import DashboardDependencies, build_dashboard


def test_dashboard_preserves_official_data_when_decision_fails():
    deps = DashboardDependencies(
        team=lambda team_id: {"team_id": team_id, "name": "Test XI", "event": 2, "picks": []},
        live=lambda team_id: {"current_event": 2, "status": "LIVE", "picks": []},
        history=lambda team_id: {"history": []},
        fixtures=lambda team_id: {"fixtures": []},
        players=lambda: {"players": []},
        decision=lambda team_id: (_ for _ in ()).throw(RuntimeError("model offline")),
    )
    payload = build_dashboard(44, deps)
    assert payload["data"]["team"]["name"] == "Test XI"
    assert payload["data"]["decision"] is None
    assert payload["errors"] == [{"area": "decision", "message": "Decision data is unavailable"}]
```

- [ ] **Step 2: Run the focused test and confirm failure**

Run: `python -m pytest tests/test_dashboard_service.py -q`

Expected: FAIL because the service does not exist.

- [ ] **Step 3: Implement dependency-injected composition**

Create a frozen `DashboardDependencies` dataclass. Build official team data first because it validates the Team ID. Load live, history, fixtures, explorer players, and decision data independently; catch only known service/data exceptions plus `RuntimeError`, add a stable area-level error, and retain successful areas. Add metadata with current event, ISO UTC generation time, and a `degraded` boolean.

- [ ] **Step 4: Add the versioned FastAPI route**

```python
@app.get("/api/v1/dashboard/{team_id}")
def get_dashboard_v1(team_id: int):
    if team_id <= 0:
        raise HTTPException(status_code=400, detail="team_id must be positive")
    try:
        return build_dashboard(team_id)
    except TeamServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
```

- [ ] **Step 5: Test service and route contracts**

Run: `python -m pytest tests/test_dashboard_service.py tests/test_decision_api.py -q`

Expected: all pass, including legacy decision endpoint coverage.

- [ ] **Step 6: Commit the task**

```bash
git add backend/dashboard_service.py backend/main.py tests/test_dashboard_service.py tests/test_decision_api.py
git commit -m "feat: compose resilient live dashboard API"
```

### Task 4: Current Prediction Manifest and Status

**Files:**
- Create: `backend/data_manifest.py`
- Create: `tests/test_data_manifest.py`
- Create: `historical_data/current_data/manifest.json`
- Modify: `backend/main.py`
- Modify: `historical_data/current_data/predict_gw.py`

**Interfaces:**
- Consumes: a JSON manifest containing `season`, `prediction_event`, `prediction_file`, `generated_at`, `player_count`, and `schema_version`.
- Produces: `load_current_manifest(path) -> PredictionManifest` and `GET /api/v1/status`.

- [ ] **Step 1: Write manifest validation tests**

```python
import json
from backend.data_manifest import load_current_manifest


def test_manifest_requires_existing_prediction_file(tmp_path):
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps({
        "season": "2026-27", "prediction_event": 3,
        "prediction_file": "gw3_predictions_v11.csv",
        "generated_at": "2026-08-31T18:00:00+00:00",
        "player_count": 626, "schema_version": 1,
    }), encoding="utf-8")
    try:
        load_current_manifest(path)
    except ValueError as exc:
        assert "prediction file does not exist" in str(exc)
    else:
        raise AssertionError("missing artifact was accepted")
```

- [ ] **Step 2: Run the manifest test and confirm failure**

Run: `python -m pytest tests/test_data_manifest.py -q`

Expected: FAIL because the loader does not exist.

- [ ] **Step 3: Implement strict manifest parsing**

Use a frozen dataclass. Require a positive event, positive player count, schema version `1`, timezone-aware ISO timestamp, and a prediction file resolved within the manifest directory. Do not fall back to a glob when a manifest exists but is invalid.

- [ ] **Step 4: Publish the existing validated GW3 v11 artifact in the manifest**

Record the current 2026-27 season, event 3, exact row count from `gw3_predictions_v11.csv`, its generation timestamp, and schema version 1. Extend `predict_gw.py` so a successful prediction write atomically replaces `manifest.json` through a sibling temporary file.

- [ ] **Step 5: Add status endpoint coverage**

`GET /api/v1/status` returns official current/next event data, player count, prediction event/version/generated time, and service state `ready`, `degraded`, or `unavailable`.

- [ ] **Step 6: Run manifest, loader, and API tests**

Run: `python -m pytest tests/test_data_manifest.py tests/test_data_loader.py tests/test_app.py -q`

Expected: all pass.

- [ ] **Step 7: Commit the task**

```bash
git add backend/data_manifest.py backend/main.py historical_data/current_data/manifest.json historical_data/current_data/predict_gw.py tests/test_data_manifest.py
git commit -m "feat: publish validated current prediction manifest"
```

### Task 5: Typed Frontend Client and Test Harness

**Files:**
- Create: `frontend/lib/contracts.ts`
- Create: `frontend/lib/api.ts`
- Create: `frontend/lib/api.test.ts`
- Create: `frontend/vitest.config.ts`
- Create: `frontend/vitest.setup.ts`
- Modify: `frontend/package.json`
- Modify: `frontend/tsconfig.json`

**Interfaces:**
- Consumes: `/api/v1/dashboard/{team_id}` and `/api/v1/status` envelopes.
- Produces: `fetchDashboard(teamId, signal?) -> Promise<DashboardEnvelope>` and source-aware TypeScript contracts.

- [ ] **Step 1: Add Vitest and Testing Library scripts and dependencies**

Add `test: "vitest run"` and `test:watch: "vitest"`. Add `vitest`, `jsdom`, `@testing-library/react`, `@testing-library/jest-dom`, and `@testing-library/user-event` as dev dependencies. Configure the `@/*` alias and jsdom setup.

- [ ] **Step 2: Write the failing API client test**

```ts
import { afterEach, expect, test, vi } from "vitest";
import { fetchDashboard } from "./api";

afterEach(() => vi.restoreAllMocks());

test("rejects a non-numeric team id before fetching", async () => {
  const fetchSpy = vi.spyOn(globalThis, "fetch");
  await expect(fetchDashboard("abc")).rejects.toThrow("numeric FPL Team ID");
  expect(fetchSpy).not.toHaveBeenCalled();
});
```

- [ ] **Step 3: Run the test and confirm failure**

Run from `frontend`: `pnpm test -- lib/api.test.ts`

Expected: FAIL because `lib/api.ts` does not exist.

- [ ] **Step 4: Implement exact contracts and API client**

Define `SourceClass`, `SourceMeta`, `AreaError`, `DashboardTeam`, `DashboardLive`, `DashboardDecision`, `DashboardData`, and `DashboardEnvelope`. Validate Team ID with `/^\d+$/`, fetch with `cache: "no-store"`, parse error detail, and throw `ApiError(status, message)`.

- [ ] **Step 5: Run frontend tests and type check**

Run from `frontend`: `pnpm test -- lib/api.test.ts && pnpm exec tsc --noEmit`

Expected: all pass.

- [ ] **Step 6: Commit the task**

```bash
git add frontend/package.json frontend/pnpm-lock.yaml frontend/tsconfig.json frontend/vitest.config.ts frontend/vitest.setup.ts frontend/lib/contracts.ts frontend/lib/api.ts frontend/lib/api.test.ts
git commit -m "feat: add typed dashboard client"
```

### Task 6: Team Session and Responsive Application Shell

**Files:**
- Create: `frontend/app/providers/TeamProvider.tsx`
- Create: `frontend/app/providers/TeamProvider.test.tsx`
- Create: `frontend/components/shell/AppShell.tsx`
- Create: `frontend/components/shell/AppShell.test.tsx`
- Create: `frontend/components/states/DataState.tsx`
- Modify: `frontend/app/layout.tsx`
- Modify: `frontend/app/globals.css`

**Interfaces:**
- Consumes: `fetchDashboard`, local storage key `fpl-ai-team-id`, and Next.js pathname.
- Produces: `useTeam()` with `teamId`, `dashboard`, `loading`, `error`, `connect`, `disconnect`, and `refresh`; `AppShell` wraps all connected routes.

- [ ] **Step 1: Write provider persistence and shell-navigation tests**

```tsx
test("connect persists a valid Team ID and loads the dashboard", async () => {
  const user = userEvent.setup();
  render(<TeamProvider><Probe /></TeamProvider>);
  await user.type(screen.getByLabelText(/team id/i), "123");
  await user.click(screen.getByRole("button", { name: /connect/i }));
  expect(localStorage.getItem("fpl-ai-team-id")).toBe("123");
  expect(await screen.findByText("Test XI")).toBeInTheDocument();
});
```

Assert that the shell exposes Overview, My Team, Plan, Explore, and Settings as links and has a visible data-freshness label.

- [ ] **Step 2: Run the focused component tests and confirm failure**

Run from `frontend`: `pnpm test -- app/providers components/shell`

Expected: FAIL because provider and shell do not exist.

- [ ] **Step 3: Implement the provider state machine**

Load local storage once after mount. Abort superseded requests. Keep successful dashboard data visible during background refresh. Refresh every 60 seconds only when the document is visible. A disconnect clears storage and in-memory data.

- [ ] **Step 4: Implement application shell and shared states**

Desktop uses the five-destination rail. Below 760 px it becomes a bottom navigation with 44 px targets. Add a deadline/gameweek header, source/freshness text, skip link, `aria-current`, and a visible degraded banner driven by `dashboard.meta.degraded`.

- [ ] **Step 5: Install provider in root layout and replace ad-hoc global styles with tokens**

Keep dark-first colors, violet product accent, green live status, amber risk, and red errors. Add `prefers-reduced-motion`, `:focus-visible`, responsive layout, and tabular number utilities.

- [ ] **Step 6: Run provider/shell tests and type check**

Run from `frontend`: `pnpm test -- app/providers components/shell && pnpm exec tsc --noEmit`

Expected: all pass.

- [ ] **Step 7: Commit the task**

```bash
git add frontend/app/providers frontend/components/shell frontend/components/states frontend/app/layout.tsx frontend/app/globals.css
git commit -m "feat: add responsive FPL application shell"
```

### Task 7: Premium Overview Decision Hierarchy

**Files:**
- Create: `frontend/components/dashboard/OverviewDashboard.tsx`
- Create: `frontend/components/dashboard/OverviewDashboard.test.tsx`
- Modify: `frontend/app/page.tsx`
- Modify: `frontend/components/dashboard/GameweekHeader.tsx`
- Modify: `frontend/components/dashboard/StatsGrid.tsx`
- Modify: `frontend/components/dashboard/RankTrend.tsx`
- Modify: `frontend/components/dashboard/ConnectTeam.tsx`

**Interfaces:**
- Consumes: `DashboardEnvelope` from `useTeam()`.
- Produces: connected Overview, connection empty state, and degraded official-only view.

- [ ] **Step 1: Write overview behavior tests**

Test these exact states with fixture envelopes:

- disconnected: numeric Team ID form is the primary action;
- connected/live: live points and `Live` source label are visible;
- connected/model: recommendation displays net gain, confidence when supplied, and `Model` label;
- degraded decision: team/pitch remains visible and recommendation panel says model analysis is unavailable;
- stale: last refresh time and stale label are visible.

- [ ] **Step 2: Run the overview test and confirm failure**

Run from `frontend`: `pnpm test -- components/dashboard/OverviewDashboard.test.tsx`

Expected: FAIL because the component does not exist.

- [ ] **Step 3: Implement Overview using the fixed hierarchy**

Render in this order: gameweek/deadline, live score or next projection, primary recommendation, compact team pitch, rank trend, upcoming fixtures, captain shortlist, then risks/opportunities. Use `?? "—"` for missing values, never hardcoded sample data, and keep one primary action.

- [ ] **Step 4: Make the route thin**

```tsx
"use client";
import { OverviewDashboard } from "@/components/dashboard/OverviewDashboard";

export default function Page() {
  return <OverviewDashboard />;
}
```

- [ ] **Step 5: Run overview tests, lint, and type check**

Run from `frontend`: `pnpm test -- components/dashboard && pnpm lint && pnpm exec tsc --noEmit`

Expected: all pass with no ESLint warnings.

- [ ] **Step 6: Commit the task**

```bash
git add frontend/app/page.tsx frontend/components/dashboard
git commit -m "feat: rebuild premium live overview"
```

### Task 8: Functional My Team Workspace

**Files:**
- Create: `frontend/app/team/page.tsx`
- Create: `frontend/components/team/TeamPitch.tsx`
- Create: `frontend/components/team/TeamPitch.test.tsx`
- Modify: `frontend/app/teamSelection.ts`
- Modify: `frontend/app/globals.css`

**Interfaces:**
- Consumes: team picks, live pick stats, predictions, and model preferred XI from `DashboardEnvelope`.
- Produces: accessible live/projected modes and valid local XI swaps without mutating the official squad.

- [ ] **Step 1: Write pitch interaction tests**

Assert that fifteen players render, captain and vice-captain have text labels, live/projected mode changes displayed points, an invalid goalkeeper/outfield swap is rejected with an alert, and a valid bench swap updates the local XI.

- [ ] **Step 2: Run the pitch test and confirm failure**

Run from `frontend`: `pnpm test -- components/team/TeamPitch.test.tsx`

Expected: FAIL because `TeamPitch` does not exist.

- [ ] **Step 3: Implement semantic pitch and bench**

Use real buttons for players, `aria-pressed` for selected swap source, and a live region for formation feedback. Reuse `isValidStartingXI`. Drag-and-drop is an enhancement; click-to-swap is the complete keyboard/touch path.

- [ ] **Step 4: Add thin route and responsive styles**

The pitch uses position rows above 760 px and a compact ordered list at narrow widths. The bench remains visually separate. Player details open in an in-flow drawer/dialog with name, team, price, opponent, points, minutes, projection, and risk.

- [ ] **Step 5: Run team tests and type check**

Run from `frontend`: `pnpm test -- components/team app/teamSelection && pnpm exec tsc --noEmit`

Expected: all pass.

- [ ] **Step 6: Commit the task**

```bash
git add frontend/app/team frontend/components/team frontend/app/teamSelection.ts frontend/app/globals.css
git commit -m "feat: add accessible live team workspace"
```

### Task 9: Functional Plan Workspace

**Files:**
- Create: `frontend/app/plan/page.tsx`
- Create: `frontend/components/plan/PlanWorkspace.tsx`
- Create: `frontend/components/plan/PlanWorkspace.test.tsx`
- Modify: `backend/dashboard_service.py`
- Modify: `tests/test_dashboard_service.py`

**Interfaces:**
- Consumes: existing decision engine `transfers`, `captain`, `vice_captain`, `starting_xi`, bench, risk, and horizon fields.
- Produces: transfer, captain, chip availability, and multi-gameweek panels; absent structured fields render honest unavailable states.

- [ ] **Step 1: Extend dashboard composition contract tests**

Assert that decision output is passed through without renaming numerical fields and that model metadata includes the prediction artifact version.

- [ ] **Step 2: Write Plan component tests**

Assert that zero-transfer/hold is rendered as a valid recommendation, hit cost is subtracted in the shown net gain, captain and vice-captain are labeled, alternatives are buttons, and absent chip/horizon data is labeled unavailable rather than synthesized.

- [ ] **Step 3: Run focused tests and confirm Plan failure**

Run: backend `python -m pytest tests/test_dashboard_service.py -q`; frontend `pnpm test -- components/plan`

Expected: backend contract passes after fixture extension; frontend fails because Plan does not exist.

- [ ] **Step 4: Implement Plan workspace and route**

Use tabs or segmented buttons for Transfers, Captaincy, Chips, and Horizon. Keep Transfers selected initially. Show one recommended move, net expected gain, price/bank impact, rationale list, and alternatives. Do not place model confidence on fields that do not provide it.

- [ ] **Step 5: Run backend and frontend Plan tests**

Run: `python -m pytest tests/test_dashboard_service.py tests/test_decision_engine.py -q`; from frontend: `pnpm test -- components/plan && pnpm exec tsc --noEmit`

Expected: all pass.

- [ ] **Step 6: Commit the task**

```bash
git add backend/dashboard_service.py tests/test_dashboard_service.py frontend/app/plan frontend/components/plan
git commit -m "feat: add structured FPL planning workspace"
```

### Task 10: Functional Explore and Settings Workspaces

**Files:**
- Create: `frontend/app/explore/page.tsx`
- Create: `frontend/app/settings/page.tsx`
- Create: `frontend/components/explore/ExploreWorkspace.tsx`
- Create: `frontend/components/explore/ExploreWorkspace.test.tsx`
- Create: `frontend/components/settings/SettingsWorkspace.tsx`
- Modify: `backend/main.py`
- Create: `tests/test_explorer_api.py`

**Interfaces:**
- Consumes: official/live player ranking, fixtures, source metadata, and TeamProvider actions.
- Produces: filterable player/fixture views and connection/data settings.

- [ ] **Step 1: Add versioned explorer endpoint tests**

Test `GET /api/v1/players?position=MID&limit=20` validation, source metadata, and stable empty results; test `GET /api/v1/fixtures?team_id=123&limit=10` validation and chronological ordering.

- [ ] **Step 2: Implement versioned explorer routes using existing services**

Wrap `get_live_players` and `get_upcoming_team_fixtures` in the standard envelope. Do not duplicate their normalization logic.

- [ ] **Step 3: Write Explore component tests**

Assert position filter behavior, Official/Live/Model labels, player comparison selection limited to four, fixture chronological order, and an explicit empty state.

- [ ] **Step 4: Implement Explore and Settings**

Explore initially shows live players plus upcoming fixtures and supports All/GKP/DEF/MID/FWD filters. Settings shows current Team ID, disconnect/switch action, API base URL, last refresh, prediction version, and the public-data/model disclaimer.

- [ ] **Step 5: Run explorer and settings verification**

Run: `python -m pytest tests/test_explorer_api.py backend/tests/test_live_api.py -q`; from frontend: `pnpm test -- components/explore components/settings && pnpm exec tsc --noEmit`

Expected: all pass.

- [ ] **Step 6: Commit the task**

```bash
git add backend/main.py tests/test_explorer_api.py frontend/app/explore frontend/app/settings frontend/components/explore frontend/components/settings
git commit -m "feat: add player explorer and data settings"
```

### Task 11: Product Verification and Operational Handoff

**Files:**
- Create: `docs/PREMIUM_DASHBOARD.md`
- Modify: `frontend/README.md`
- Modify: `README.md`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: the complete vertical slice.
- Produces: reproducible local startup, test, refresh, and source-label documentation.

- [ ] **Step 1: Run complete deterministic backend suite**

Run: `python -m pytest tests backend/tests -q`

Expected: all tests pass; network is mocked in deterministic tests.

- [ ] **Step 2: Run frontend quality gates**

Run from `frontend`: `pnpm test && pnpm lint && pnpm build`

Expected: tests, ESLint, type checking within the production build, and route generation pass.

- [ ] **Step 3: Run real FPL smoke checks**

Start FastAPI locally, call `/api/v1/status`, then call `/api/v1/dashboard/{known-public-team-id}` with a user-supplied or locally configured smoke Team ID. Verify current event, 20 teams, a non-zero official player count, response timestamps, and either decision data or an explicit degraded decision error.

- [ ] **Step 4: Inspect responsive UI**

Start Next.js and inspect Overview, My Team, Plan, Explore, and Settings at 1440×900, 768×1024, and 390×844. Verify no horizontal page overflow, the bottom navigation at mobile width, keyboard-only Team ID connection and pitch swaps, visible focus, and readable stale/degraded states.

- [ ] **Step 5: Document exact startup and data semantics**

Document backend and frontend commands, `NEXT_PUBLIC_API_URL`, Team ID connection, live refresh behavior, manifest refresh, source classes, failure modes, and the fact that model values are estimates rather than official FPL values. Add `.superpowers/` to `.gitignore` because visual brainstorming artifacts are local-only.

- [ ] **Step 6: Run diff and secret checks**

Run: `git diff --check` and `rg -n "password|secret|api[_-]?key|token" -g '!*.csv' -g '!fpl.db' .`

Expected: no whitespace errors and no newly introduced credentials.

- [ ] **Step 7: Commit documentation**

```bash
git add README.md frontend/README.md docs/PREMIUM_DASHBOARD.md .gitignore
git commit -m "docs: add premium dashboard operations guide"
```
