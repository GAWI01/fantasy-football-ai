# PRD implementation status

Updated: 2026-09-02

This is the authoritative gap register for `FPL-AI_MVP_PRD.docx`. A green automated test proves only the behavior named by that test; it does not close a broader PRD requirement by implication.

| PRD area | Status | Current evidence | Remaining release evidence |
|---|---|---|---|
| Public Team ID connection | Implemented | Numeric validation, local browser persistence, real `/api/v1/dashboard/{team_id}` loading, official manager/team identity and clear loading/error/degraded states | Interactive invalid-ID browser QA |
| One clear GW plan | Implemented | Transfer/HOLD, cost/hit, captain/vice, legal XI/bench, chip HOLD bias, confidence, evidence, best alternatives and five-GW horizon | Calibrate decisions against future production outcomes |
| Deadline/live mode | Implemented | Official next-deadline countdown, automatic LIVE/FINISHED emphasis, cache-first source badges that reserve `Live` for a genuinely active and fresh Gameweek, a phase-aware Gameweek-points KPI and Current XI that switches from model xPts to actual player points during live play, relevant live fixtures and an owned-player event surface for goals, assists, saves, cards, penalty outcomes and provisional bonus; impossible post-deadline transfer math is hidden and chip state remains available read-only | Re-check at a live deadline transition in hosted staging |
| Interactive 15-player squad | Implemented | All 15 picks, current/model XI comparison, captain badges, automatic projected-before-deadline/live-during-GW mode plus a manual toggle, honest unknown (`—`) rather than fabricated zero when an official live value is absent, price on every card, legally safer club-colour kit abstractions, formation-safe desktop drag-and-drop plus click/touch swaps, bench reorder and player drill-down with xPts, xMins, fixture, risk, official form, ownership and season evidence | Mouse/touch viewport QA on real devices |
| Decision engine | Implemented | Legal squad/XI, transfers, captain, risk, official chip state, adaptive bench value and five-GW fixtures served by `/api/v1/plan/{team_id}` | Outcome calibration and broader multi-transfer search are post-MVP improvements |
| Player risk/news | Implemented (MVP) | Official FPL availability/status/news, xMins, start probability, rotation risk and source labels; weak rumours are intentionally excluded | Add another source only after legal, confidence and baseline evaluation |
| Dashboard hierarchy | Implemented | Premium Overview, phase-correct live/model/official/derived KPIs with consistent Cached override across official/live widgets, a live-score fallback that refuses to present a partial pick feed as a complete team total, rank trend, squad readiness, primary decision, an XI with contextual actual-versus-projected player values, fixtures, captain, owned-team events, actual GW leaders, form watch and action radar | Visual viewport QA |
| Transfer Center / What-if | Implemented | Deep-linked Transfer Center compares the recommended route, an explicit roll/HOLD baseline, hit costs, legal transfer alternatives and owned-player captain variants across next-GW and five-GW value; bench/lineup simulation links directly to My Team and nothing writes to FPL | Save/share and custom multi-transfer editing are later SaaS features |
| Chips | Implemented | Public manager chip history drives current half-season availability; unavailable/unknown is conservative and HOLD is default | Calibrate opportunity thresholds over more completed Gameweeks |
| Multi-GW planning | Implemented | GW+1 is native model output; GW+2..GW+5 are explicitly labeled fixture-scaled estimates using official home/away/FDR, blanks/doubles and increasing uncertainty | Independently trained future-GW projections are a model upgrade, not an MVP blocker |
| Explore / Players / Fixtures | Implemented | Works with or without Team ID; actual GW points/minutes/goals/assists/bonus/BPS, official season xG/xA/xGI/ICT, model xPts/xMins, form, price, ownership, official status/news, four-player shortlist, URL state and all-team five-GW blank/double matrix; player-market badges derive `Live`/`Official` from the returned Gameweek phase and `Cached` from freshness | Visual viewport QA |
| Loading / empty / partial states | Implemented | Shared accessible loading state reserves layout with an animated skeleton on Overview, My Team, Plan, Explore and Review; automatic saved-Team-ID restoration and its error branch remain distinct from first-time onboarding on My Team and Review; reduced-motion CSS suppresses repeated animation; empty, stale, degraded and failed-secondary-source paths remain explicit | Confirm perceived layout stability in interactive browser QA |
| Settings / local preferences | Implemented | Team ID, data trust/provenance and a locally persisted season goal; mini-league success is the default and changes strategic framing without altering official facts or model projections | Browser persistence QA across tabs |
| Performance / refresh | Implemented locally | Visible connected dashboards refresh every 60 seconds; complete two-transfer search and 623-player five-GW horizon have explicit latency regressions; a fresh real-Team-ID FastAPI dashboard smoke completed in 1.432s with 15 picks, decision data and no errors/stale/degraded state (previously 14–17s) | Measure cold/warm p50/p95 from the final hosted region before launch |
| Meaningful plan changes | Implemented | Local-only plan snapshots ignore small model-only movements and expose PLAN CHANGED with old/new action, reason, time and updated uncertainty | Browser persistence QA across a real pre-deadline model refresh |
| Post-GW AI review | Implemented | Stored pre-deadline artifact versus official actuals, hits, captain, bench, transfers, largest points miss and xMins-versus-official-minutes miss; decision quality is rated only from pre-deadline expected value/cost and remains independent of noisy actual points; deterministic evidence-backed next-GW signals are exposed; unfinished GWs and missing/legacy fields are handled honestly | First full live xMins outcome is available after a GW with the current certified xMins artifact finishes |
| Navigation/deep links | Implemented | Full PRD desktop destinations point to functional deep-linked surfaces; mobile uses four primary destinations plus an accessible More sheet exposing every remaining PRD destination with focus trap, Escape close and focus return; AppShell has a permanent automated WCAG A/AA semantics regression scan | Browser back/scroll and physical keyboard QA |
| Public deployment engineering | Implemented | Same-origin-safe API default, environment URL/CORS, timeouts/cache/stale fallback, health/readiness, JSON request logs, request IDs, non-root Dockerfiles, Compose, Render blueprint and runbook; local production-mode backend/frontend processes pass HTTP and CORS smoke | Build containers on a Docker-enabled host and run hosted HTTPS smoke |
| Data provenance and rights | Release-gated | Source classes/register, freshness, independent-beta disclaimer and a 2026-09-02 re-review of the official terms; the permission request now enumerates endpoints, fields, caching, derived output, branding and match-data scope | Written permission or licensed data source before a public/paid launch |
| Verification gate | Locally passed | 343 backend tests, 87 frontend tests, ESLint, standalone TypeScript through the production build, configured production build, automated WCAG A/AA scans across AppShell, Overview, My Team, Plan, Explore, Review and Settings; the actual Next standalone artifact serves all six core routes plus eight PRD legacy routes and a static asset with HTTP 200; configured-origin CORS and request IDs pass across the live API; fresh official FPL smoke is ready with a 1.432s enriched Team-ID dashboard response and a 0.532s plan response, 20 teams, 15 picks, official form/ownership/season/xG evidence, decision available and no errors/stale/degraded; the player market returns xG and ICT for all 629 players; live returns 15 picks and 20 official owned-player aggregate events; model manifest covers 623 GW3 predictions | Visual contrast, responsive interaction and physical keyboard/touch QA unavailable because no browser backend is connected; Docker, Podman, nerdctl and Buildah are unavailable |

## External release gates

1. Run desktop, common-phone, touch, keyboard and browser-history QA when an interactive browser backend or physical devices are available. Browser discovery was revalidated on 2026-09-02 and returned no connected backends.
2. Build and health-check both containers on a Docker-enabled CI/deployment host, then run the documented HTTPS smoke against real service URLs.
3. Clear `docs/DATA_USE_RELEASE_GATE.md` before any public or paid launch.

## Hosted staging preparation — 2026-10-01

Branch: `deploy/staging-readiness`; local implementation only, no push/deploy.
The September verification table above is historical evidence, not hosted QA.

- Backend Docker context now permits only serving code and the explicit eight-file
  data bundle; secrets, training artifacts and developer state are excluded.
- The five previously ignored serving CSVs have explicit Git exceptions. The
  existing GW3 timestamp/manifest is preserved; no current-GW refresh is claimed.
- Status validates artifact structure, exposes generation/target GW fields and
  degrades on target mismatch or stale upstream; liveness remains separate.
- Backend runtime dependencies are pinned separately from research/test tooling;
  frontend uses pnpm 11.25.0 and its unchanged lockfile exclusively.
- Local checks: 361 Python tests passed (one existing pandas FutureWarning),
  87 frontend tests passed, frozen install, lint, TypeScript and configured
  production build passed. Standalone output served six core routes plus a JS
  asset with HTTP 200. Serving-only temporary-copy validation/import passed.
- Docker is not installed: Compose config/build and Linux container verification
  remain unrun. Hosted HTTPS/device/access-control QA remains outstanding.
- Data-use gate remains unchanged. See DEPLOYMENT.md and PROJECT_HANDOFF.md.

### Pre-commit corrections — 2026-10-03

The final review identified over-broad Docker parent-directory exceptions and
invalid UTF-8 dash bytes in the handoff/status documents. The directory
exceptions were removed and file exceptions retained. Encoding was corrected.
New regressions cover directory reinclusion, the exact eight-file data bundle,
and strict UTF-8 decoding. The targeted deployment/status/runtime-artifact suite
passed 26 tests after these fixes; git diff --check passed. No new full-suite or
frontend build run was needed. Docker image verification, hosted private access,
current-GW artifact publication and the public data-use gate remain outstanding.
