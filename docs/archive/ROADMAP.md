# ROADMAP.md

## Phase 0 — Cleanup / understanding
- [ ] Inspect the complete existing repository
- [ ] Identify reusable data/feature/prediction code
- [ ] Move V1–V5 experiments to `legacy/`
- [ ] Establish current entry points
- [ ] Add requirements/setup documentation

## Phase 1 — Fast optimizer
- [ ] Implement MILP/ILP optimizer
- [ ] Encode all core FPL constraints
- [ ] Add starting XI and bench
- [ ] Add captain/vice-captain
- [ ] Add tests for budget, squad size, positions and max-3-club rule
- [ ] Benchmark against current brute-force versions
- [ ] Target seconds, not minutes

## Phase 2 — Better player modelling
- [ ] xG/xA
- [ ] shots and chances
- [ ] key passes/creation
- [ ] defensive contribution / DefCon
- [ ] set-piece involvement
- [ ] penalty involvement
- [ ] player role/position context
- [ ] goalkeeper save/CS inputs
- [ ] team attacking/defensive strength

## Phase 3 — xMins / risk
- [ ] Proper xMins model
- [ ] Start probability
- [ ] injury/availability signal
- [ ] rotation/congestion
- [ ] return-from-injury handling
- [ ] uncertainty estimate

## Phase 4 — Multi-GW
- [ ] GW+1 to GW+5 forecasts
- [ ] decreasing future weights
- [ ] fixture-run context
- [ ] long-term hold value
- [ ] avoid unnecessary future transfers

## Phase 5 — Decision engine
- [ ] Current squad input
- [ ] normal transfer optimizer
- [ ] captaincy model
- [ ] Wildcard decision model
- [ ] Free Hit
- [ ] Bench Boost
- [ ] differential/aggressive mode
- [ ] ownership/EO

## Phase 6 — Validation
- [ ] Historical prediction backtest
- [ ] xMins backtest
- [ ] optimizer backtest
- [ ] captain backtest
- [ ] transfer backtest
- [ ] chip backtest
- [ ] compare model versions quantitatively

## Phase 7 — Weekly automation
- [ ] One weekly runner
- [ ] Structured JSON output
- [ ] Human-readable weekly report
- [ ] Optional AI API call
- [ ] Logging
- [ ] Error handling
- [ ] Cached data where appropriate

## Phase 8 — GitHub release
- [ ] Clean README
- [ ] Architecture documentation
- [ ] Setup instructions
- [ ] Example output
- [ ] Tests
- [ ] License
- [ ] Data-source documentation
- [ ] Legacy versions separated
- [ ] Remove secrets/API keys
- [ ] Reproducible setup
