# Post-Gameweek Review Implementation Plan

> Status: Approved continuation of the premium live SaaS dashboard design and PRD.

**Goal:** Add a trustworthy post-Gameweek review that compares the manager's official result with the exact historical model artifact available for that Gameweek.

**Architecture:** Keep the calculation deterministic in a pure backend service. The API composes official FPL history, event live data, manager transfers, bootstrap metadata, and the highest-versioned prediction artifact. The frontend consumes the structured result on a dedicated secondary route so the main dashboard stays fast.

**Constraints:** Never invent retrospective AI reasoning. Missing historical predictions return an explicit unavailable state. The review is only available for a finished Gameweek. Existing uncommitted user work must be preserved. Git commits are omitted because repository identity is not configured.

---

## Task 1: Pure review calculation and artifact selection

**Files:**
- Create: `backend/review_service.py`
- Create: `tests/test_review_service.py`

1. Write failing tests for projected versus official points, hit cost, captain contribution, bench points, transfer deltas, largest residual, deterministic outcome labels, and highest-versioned artifact selection.
2. Run the focused test file and confirm the failures are caused by the missing service.
3. Implement the smallest pure calculation and validation layer that makes the tests pass.
4. Re-run the focused test file.

## Task 2: Official historical readers and review API

**Files:**
- Modify: `backend/live_service.py`
- Modify: `backend/main.py`
- Modify: `tests/test_live_service.py`
- Create: `tests/test_review_api.py`

1. Write failing tests for historical picks, transfers, event live data, latest finished event, the successful review envelope, unfinished events, and missing prediction artifacts.
2. Add validated public readers around the existing cached FPL gateway.
3. Add `GET /api/v1/review/{team_id}` with an optional `event` query parameter.
4. Return structured source metadata and an explicit `available: false` result when an honest review cannot be built.
5. Re-run the focused backend tests.

## Task 3: Premium review interface

**Files:**
- Modify: `frontend/lib/contracts.ts`
- Modify: `frontend/lib/api.ts`
- Create: `frontend/components/review/PostGameweekReview.tsx`
- Create: `frontend/components/review/PostGameweekReview.test.tsx`
- Create: `frontend/app/review/page.tsx`
- Modify: `frontend/components/overview/OverviewDashboard.tsx`
- Modify: `frontend/app/globals.css`

1. Write failing component and client tests for loading, unavailable, and complete review states.
2. Add the typed API contract and client method.
3. Implement the review page with outcome, captain, transfer, bench, and model-miss sections.
4. Add a secondary Overview entry point without changing the five-item primary navigation.
5. Run focused tests and TypeScript checking.

## Task 4: Documentation and verification

**Files:**
- Modify: `docs/PRD_IMPLEMENTATION_STATUS.md`

1. Update the PRD gap register with the implemented review behavior and remaining limitations.
2. Run the complete backend and frontend test suites, lint, type checking, and production build.
3. Smoke-test the live review endpoint against the official public FPL API.
4. Report browser-only QA separately if the interactive browser backend remains unavailable.
