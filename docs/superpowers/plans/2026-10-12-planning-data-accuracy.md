# Planning and data accuracy implementation plan

**Goal:** Make transfer recommendations and their displayed arithmetic consistent, preserve deadline-time inputs, and reuse expensive decisions safely.

**Architecture:** Extend the existing Python pipeline and Next.js frontend in this repository. Keep the documented Vaastav attribution. Preserve the conservative transfer policy unless a reproducible correctness issue requires a change; forecasts already vary by Gameweek.

**Tech stack:** Python 3.12+, FastAPI, pandas, SciPy/HiGHS; Next.js 16.4, React 19.3, TypeScript, Vitest.

**Approved scope:** The user's request to fix the review in this conversation. No merge or production deployment is included.

## Constraints and review focus

- Forecast points, actual hit costs, horizon weights and policy penalties must be distinguishable.
- Recommended current moves and the displayed follow-up must describe the same squad sequence.
- Failed or incomplete solves must not claim complete optimality.
- Snapshots must record actual UTC acquisition times, target Gameweek, raw responses, source URLs and SHA256 hashes, and must never relabel post-deadline inputs as pre-deadline.
- Store raw snapshots outside Git; use immutable GitHub release assets for the scheduled archive, with no automated workflow dispatch during implementation.
- Cached decisions must change when any optimized input changes; concurrent equivalent requests should share one calculation and failures must permit retry.
- Retain all existing data permissions and source credits. Do not retrain or certify a new model on already-inspected evaluation results.

## Task 1: Planner consistency and auditable values

Files: `optimizer/two_week.py`, `optimizer/action_planner.py`, `engine/transfer_analysis.py`, related optimizer tests.

- [ ] Reproduce whether next-week moves can be paired with a different current squad than the recommendation.
- [ ] Add a failing regression for that real behavior and for distinct Gameweek projections.
- [ ] Fix the sequence coupling and report the conservative selection policy accurately.
- [ ] Expose additive unweighted projected gains after real hits separately from weighted decision scores; expose two-stage score components and search completeness.
- [ ] Verify arithmetic and run optimizer/decision tests, including recorded-team benchmarks.

## Task 2: Frontend score explanation

Files: `frontend/lib/contracts.ts`, `frontend/lib/model/plan.ts`, plan/overview components and relevant Vitest tests.

- [ ] Read `frontend/AGENTS.md` and the installed Next.js documentation before edits.
- [ ] Add failing rendering tests separating projected points from decision scores and explaining conservative recommendation overrides.
- [ ] Consume Task 1's additive fields while remaining compatible with fixtures/older API payloads.
- [ ] Show next-week transfers as conditional projections; identify the multi-Gameweek scoring horizon and actual baseline.
- [ ] Run relevant component/model tests, lint and TypeScript checks.

## Task 3: Pre-deadline archive

Files: new `historical_data/deadline_snapshots.py`, tests, `.github/workflows/deadline-snapshots.yml`, snapshot documentation and source-register entry.

- [ ] Add failing tests for snapshot windows, deadline crossing, target-event mapping, hashes and immutable writes.
- [ ] Implement due-window acquisition of public bootstrap and fixtures with bounded network requests and fail-closed timing checks.
- [ ] Provide a CLI and scheduled workflow that archives complete bundles as uniquely named release assets, outside Git.
- [ ] Document actual timing, GitHub scheduling limitations, provenance, retrieval and the existing data-use boundaries.
- [ ] Run snapshot tests and inspect one read-only live capture without publishing it.

## Task 4: Decision reuse and performance

Files: `backend/main.py`, cache tests, recorded-benchmark checks.

- [ ] Measure cold and cached requests with the recorded official-data benchmark.
- [ ] Add failing regressions for horizon-input invalidation and concurrent duplicate computation.
- [ ] Include the actual horizon frames in the cache key and add per-key single-flight reuse with retry after failures.
- [ ] Verify changed team/forecast/availability/price inputs still invalidate and cached responses remain isolated.

## Task 5: Integration and review

- [ ] Correct documentation: temporal evaluation is guarded, not inherently leak-proof; historical scoring cannot be fully reconstructed without missing components; transition to self-collected training data is evidence-based.
- [ ] Run the full Python and frontend suites, lint, type check and production build.
- [ ] Obtain an independent review of the complete diff and fix consequential findings.
- [ ] Commit and open a reviewable pull request, reporting actual checks and remaining operational requirements.
