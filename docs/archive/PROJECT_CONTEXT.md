# PROJECT_CONTEXT.md

## Purpose

This file gives an AI coding agent the historical and strategic context needed to continue FPL-AI without relying on the previous chat.

## Project history

We are building FPL-AI together as a script + AI system.

The Python side is responsible for objective computation:
- FPL data
- historical data
- features
- predictions
- availability/xMins
- optimization
- FPL constraints
- structured outputs

The AI side is intended to read the structured result and provide:
- interpretation
- football context
- explanation
- challenge of questionable model results
- transfer/captain/chip discussion

## What happened with V1–V5

The first Wildcard optimizer versions used brute-force combinations.

This repeatedly failed on performance rather than basic FPL logic.

V1:
- 616 players
- 492 active
- 140 optimizer candidates
- became extremely slow inside pandas/DataFrame construction.

V2:
- availability/xMins filtering reduced active candidates
- still stalled during combination processing and DataFrame construction.

V3:
- pre-built positional combinations
- 45 GKP
- 1,000 DEF
- 1,000 MID
- 816 FWD
- cross-position combination remained too expensive.

V4:
- 28 GKP
- 5,000 DEF
- 5,000 MID
- 364 FWD
- still too slow.

V5:
- 97 active candidates
- GKP 12
- DEF 30
- MID 35
- FWD 20
- 66 GKP combinations
- 8,000 DEF combinations
- 8,000 MID combinations
- 1,140 FWD combinations
- reached 526,537 possible DEF combinations and retained 15,000 partial solutions
- stalled while combining position groups.

### Final lesson

Candidate pruning alone is not the correct long-term solution.

**Replace the brute-force optimizer architecture.**

## Existing data outputs

Known working outputs:
- `gw2_predictions_v4.csv`
- `gw1_history.csv`
- `players_features_current.csv`
- `players_features_current_v2.csv`

The current data universe has been around 616 players.

GW1 history successfully retrieved 610 API records and mapped the final output to 616 players.

## Current feature work

The project has availability states such as:
- AVAILABLE
- MINOR_RISK
- RISK
- UNAVAILABLE

It also has:
- xMins
- start_probability
- rotation_risk

The first xMins implementation produced an unrealistic “VERY_HIGH” rotation-risk distribution, which is one reason xMins should become a proper predictive model rather than a collection of rules.

## Critical design decision

The external project review recommends MILP/ILP using something such as:
- PuLP
- OR-Tools / CP-SAT
- mip

The squad problem is naturally a constrained integer optimization problem.

Do not use pandas/DataFrames as the search engine. Pandas should be used for data preparation/feature work, while the solver handles the combinatorial decision problem.

## Player archetypes

The system should model routes to points.

DEF:
- offensive full-back
- defensive-action / DefCon specialist
- set-piece centre-back
- clean-sheet defender

MID:
- elite attacker
- creator
- set-piece specialist
- midfielder with defensive upside
- value midfielder

FWD:
- premium talisman
- goal scorer
- creator/forward hybrid
- value forward

GKP:
- save-heavy keeper
- clean-sheet keeper
- value keeper
- bonus/penalty-save upside where data supports it

These are analytical profiles, not hard labels that should override actual predicted points.

## Important distinction

Two players can have similar expected points but very different profiles:
- one may have a high floor
- one may have a high ceiling
- one may rely on clean sheets
- one may have DefCon floor
- one may be highly dependent on penalties
- one may be rotation-prone
- one may be a strong captaincy option

The optimizer should preserve these dimensions.

## Wildcard philosophy

There is no requirement to create a Wildcard team every Gameweek.

The system should first answer:

**Should I use the Wildcard now?**

Only if the marginal expected gain is sufficiently high should it optimize a Wildcard squad.

A Wildcard should consider multiple future Gameweeks, not only the next one.

## AI integration

Do not assume ChatGPT automatically sees the local Python project.

The intended architecture is:

Python pipeline
→ structured JSON/report
→ AI API/context
→ natural-language analysis

The JSON should eventually include things like:
- current squad
- budget
- proposed squad
- predicted points
- expected minutes
- risk/uncertainty
- player roles
- fixtures
- transfer suggestions
- captain candidates
- chip status
- reasons for selection/rejection

This creates a stable interface between computation and AI.

## Weekly workflow target

One command should eventually do:

1. fetch/update FPL data
2. update historical data
3. build features
4. calculate xMins/availability
5. generate predictions
6. calculate fixtures/context
7. optimize current squad/transfers/chips
8. write a structured weekly report
9. optionally send the report to the AI layer

## Testing philosophy

The system must be backtested before being considered reliable.

Do not optimize weights because they “look right” on one Gameweek.

Measure:
- point prediction error
- minutes prediction error
- squad points
- captain hit rate
- transfer value
- chip value
- calibration/risk
- performance by position

## Coding philosophy

Prefer:
- small modules
- clear interfaces
- deterministic/reproducible outputs
- fast execution
- tests
- logging
- configuration instead of magic constants

Avoid:
- giant monolithic scripts
- nested brute-force loops
- pandas operations inside massive search loops
- arbitrary candidate caps without validation
- adding complexity without measurable benefit

## Current strategic priority

1. Inspect existing codebase.
2. Design clean data model and interfaces.
3. Implement fast optimizer.
4. Test constraints.
5. Add point-route features.
6. Improve xMins.
7. Add uncertainty/ownership.
8. Add multi-GW planning.
9. Add transfers/captain/chips.
10. Backtest.
11. Automate weekly pipeline.
