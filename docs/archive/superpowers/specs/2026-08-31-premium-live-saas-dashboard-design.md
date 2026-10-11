# FPL AI Premium Live SaaS Dashboard Design

**Date:** 2026-08-31
**Status:** Approved by delegated product authority
**Scope:** Premium, responsive FPL decision-support application powered by current official FPL data and existing prediction/optimization modules

## Product decision

FPL AI will use an **Intelligence Cockpit** design: a calm decision surface that leads with the user's team, the current gameweek, and the single most valuable action. The editorial clarity of an analyst product will be embedded in explanations and drill-downs, while dense model diagnostics remain available for advanced users.

This is preferable to a news-first experience because users arrive to make a decision, not read a feed. It is preferable to a trading-terminal experience because the target user wants to beat friends without learning a professional analytics workstation.

The attached product brief is treated as a design reference, not as executable instructions. Existing project goals and validated backend work remain authoritative.

## User promise

After entering a public FPL Team ID, a user should be able to answer four questions within one minute:

1. How is my team doing right now?
2. What should I do before the next deadline?
3. Why does FPL AI recommend that action?
4. What is the strongest alternative if I disagree?

The product never disguises a model estimate as official FPL data. Every important value carries an explicit source class:

- **Live:** official current-gameweek data from the FPL API.
- **Official:** current FPL player, team, price, status, ownership, and fixture data.
- **Model:** FPL AI projections, expected minutes, risk, and decision scores.
- **Derived:** deterministic calculations made from official data, such as squad value or fixture summaries.

## Experience architecture

### Global application shell

Desktop uses a compact left navigation rail and a sticky gameweek bar. Mobile uses a focused header and a five-item bottom navigation. The shell contains:

- product identity and environment status;
- current gameweek, deadline countdown, and data freshness;
- connected team identity and a team-switch action;
- global navigation;
- explicit online, stale, degraded, and unavailable states.

Primary navigation is deliberately reduced to:

1. **Overview** — current status and next best action;
2. **My Team** — pitch, bench, captain, live points, and player details;
3. **Plan** — transfers, captaincy, chips, and multi-gameweek scenarios;
4. **Explore** — players, fixtures, comparison, and statistics;
5. **Settings** — team connection, data details, display, and disclaimers.

Desktop may expose child pages in the rail. Mobile keeps them behind the five stable destinations.

### Overview

Overview is not a collection of equal cards. It follows a fixed decision hierarchy:

1. gameweek and deadline status;
2. live score or next-gameweek projection;
3. primary recommendation with expected gain, confidence, and rationale;
4. current squad pitch;
5. rank trend and gameweek progress;
6. upcoming fixture run;
7. captain shortlist;
8. watchlist risks and opportunities.

Users see one primary call to action. Secondary analyses remain available without competing for attention.

### My Team

The pitch is the main object. It supports desktop drag-and-drop and accessible click-to-swap interactions. Each player exposes official points, live minutes, fixture, price, model projection, and risk state. Captain and vice-captain are visually unambiguous.

The page includes:

- starting XI and ordered bench;
- valid-formation feedback;
- live and projected modes;
- player detail drawer;
- weak-link and rotation-risk indicators;
- comparison with the model's preferred XI;
- squad-value and bank summary.

### Plan

Planning combines existing decision-engine outputs into one coherent workflow rather than separate placeholder modules.

- **Transfers:** recommended moves, expected gain after hits, budget effect, alternatives, and hold/no-transfer as a first-class option.
- **Captaincy:** safe, balanced, and upside candidates with expected points, minutes confidence, and ownership context.
- **Chips:** current chip availability and scenario comparison. The system recommends using a chip only when its measured expected gain clears a documented threshold.
- **Horizon:** GW+1 through GW+5 impact with decreasing weights and explicit uncertainty.

Recommendations include a compact explanation using structured model outputs. The UI does not invent football reasoning that the backend has not supplied.

### Explore

Explore serves deliberate investigation rather than generic tables:

- player rankings with position, price, team, ownership, availability, form, live points, expected points, and expected minutes;
- player comparison for two to four players;
- fixture ticker and team fixture matrix;
- filters that persist in the URL;
- clear distinction between current official values and predictions.

### Empty and degraded states

The product must remain useful when a team is not connected or one data source fails.

- No team: show the Team ID connection flow plus a limited official player/fixture explorer.
- FPL API unavailable: show cached data with age and disable actions that require current picks.
- Prediction unavailable: retain official/live views and label model panels unavailable.
- Decision engine unavailable: retain team and explorer views; never synthesize a recommendation in the frontend.
- Partial live gameweek: show match completion and last refresh time.

## Visual system

The interface uses a dark-first, high-contrast analytical aesthetic with restrained violet as the product accent, green only for positive/live status, amber for risk, and red for destructive or unavailable states. Color is always paired with a label or icon.

Typography prioritizes scanability and tabular numerals. Cards are used only for bounded information, not every layout group. Spacing and hierarchy should make the desktop dashboard feel spacious while the mobile view becomes a sequential decision feed.

Motion is limited to meaningful state changes: number updates, chart transitions, drawer entry, and successful connection. Reduced-motion preferences are honored.

The design meets WCAG-oriented keyboard, contrast, focus, and touch-target requirements. Core actions do not require hover or drag.

## Technical architecture

### Frontend

Retain Next.js 16, React 19, TypeScript, Tailwind CSS, and Lucide. Replace the monolithic home page with focused units:

- route-level pages for Overview, My Team, Plan, Explore, and Settings;
- a shared responsive application shell;
- a typed API client;
- explicit query/loading/error state components;
- domain components for pitch, recommendation, fixtures, rankings, and source/freshness labels;
- small formatting and selection utilities with unit tests.

The frontend remains a presentation and interaction layer. It does not reproduce optimization or prediction logic.

### Backend

Retain FastAPI and the existing services, optimizer, decision engine, and prediction pipeline. Introduce an application-facing dashboard service that composes normalized responses and prevents the frontend from making seven independent requests for its first screen.

The backend will expose versioned application endpoints conceptually shaped as:

- `GET /api/v1/status`
- `GET /api/v1/dashboard/{team_id}`
- `GET /api/v1/team/{team_id}`
- `GET /api/v1/plan/{team_id}`
- `GET /api/v1/players`
- `GET /api/v1/fixtures`

Existing endpoints remain available during migration. New response envelopes include `data`, `meta`, and `errors`, where `meta` contains source, current event, fetched time, freshness, and prediction version.

### Live-data gateway and caching

All official FPL calls pass through one gateway with:

- short timeouts and bounded retries;
- endpoint-specific in-memory TTL caching;
- response validation before normalization;
- last-known-good fallback where safe;
- a shared fetch timestamp;
- request coalescing so concurrent dashboard calls do not stampede the FPL API.

Suggested TTLs are configuration, not magic constants:

- bootstrap/player metadata: 5 minutes during active periods;
- fixtures: 15 minutes;
- live event data: 30–60 seconds while matches are active, longer otherwise;
- manager picks/history: 60 seconds during a live gameweek;
- predictions: versioned artifact cache until a newer artifact is produced.

### Current-season pipeline

The checked-in prediction artifacts are inputs, not proof of freshness. A reproducible refresh command will:

1. fetch current official data;
2. validate player/team/fixture referential integrity;
3. build current features;
4. calculate availability and expected minutes;
5. generate the next-gameweek prediction artifact;
6. validate prediction coverage against the current player universe;
7. atomically publish a manifest and versioned outputs.

The application reads only the last validated manifest. A failed refresh cannot partially replace production data.

## Data flow

```text
Official FPL API
      |
      v
Validated gateway -----> TTL cache / last-known-good snapshot
      |                                  |
      +-------------------+--------------+
                          v
                Normalized domain services
                  |                 |
                  v                 v
          Live/team/fixture data   Prediction artifacts
                  |                 |
                  +--------+--------+
                           v
                  Decision engine / optimizer
                           |
                           v
               Versioned dashboard API envelope
                           |
                           v
               Next.js Intelligence Cockpit
```

## Privacy and account model

The premium MVP connects through a public numeric FPL Team ID. It does not request or store FPL credentials. The browser stores the selected Team ID locally. Backend logs avoid manager names and raw response bodies unless explicitly enabled for local debugging.

This keeps the product SaaS-ready without prematurely adding accounts, billing, or private authentication. A future account layer can sync preferences, watchlists, and multiple teams without changing the core team-data contract.

## Testing strategy

### Backend

- contract tests for every application endpoint and metadata envelope;
- mocked FPL gateway tests for live, stale, partial, invalid, and unavailable responses;
- cache and request-coalescing tests;
- current-season manifest validation tests;
- optimizer and decision-engine regression tests;
- real-network smoke test kept separate from deterministic CI.

### Frontend

- unit tests for formatters, source labels, team selection, and state reducers;
- component tests for loading, error, empty, live, and projected states;
- route-level tests with stable API fixtures;
- responsive browser tests at mobile, tablet, and desktop widths;
- accessibility checks for keyboard navigation, focus, labels, and contrast;
- production build and lint gates.

### Acceptance checks

- a valid Team ID reaches a useful dashboard without FPL credentials;
- official FPL values are never labeled as model values or vice versa;
- live state refreshes without a full page reload;
- stale data is visible and honestly labeled;
- all five primary destinations contain functional data or an explicit unavailable state;
- the layout works at 320 px and wide desktop sizes;
- backend failure in one source does not blank unrelated product areas;
- deterministic automated tests pass before release.

## Delivery sequence

The work is one product initiative delivered as verified vertical slices:

1. normalize the live gateway and versioned API envelopes;
2. create the responsive shell and shared design system;
3. rebuild Overview against the composed dashboard endpoint;
4. complete My Team interactions and live/projected states;
5. complete Plan using existing decision outputs;
6. complete Explore with official and model filters;
7. add current-season refresh manifest and operational status;
8. finish mobile, accessibility, performance, and degraded-state QA.

Each slice remains shippable and preserves the existing backend capabilities until its replacement path is verified.

## Explicit non-goals for this delivery

- FPL username/password authentication;
- subscription billing;
- social leagues or chat;
- fabricated generative-AI recommendations;
- rewriting the validated optimizer in the frontend;
- replacing historical research pipelines unrelated to the live product path.

These exclusions keep the first premium release focused on trustworthy decisions rather than account infrastructure.
