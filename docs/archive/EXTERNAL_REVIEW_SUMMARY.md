# EXTERNAL_REVIEW_SUMMARY.md

This document summarizes the external review included with this project as `FPL-AI_Anbefalinger.pdf`.

The review's central conclusion is that the Python + AI split is sound, and that the major blocker is the brute-force optimizer rather than lack of additional features.

## Highest priority

Replace brute-force positional combination search with MILP/ILP using a solver such as PuLP, OR-Tools/CP-SAT or mip.

The review specifically recommends keeping pandas for data preparation and feature construction, not as the search engine.

## Data additions

Recommended:
- xG/xA
- set-piece information
- defensive contribution / DefCon
- better injury/news signal
- stronger fixture difficulty based on underlying performance
- ownership / Effective Ownership

## Modelling

Recommended:
- proper xMins model rather than rule-only logic
- multi-GW weighted objective
- prediction uncertainty
- safe vs aggressive risk settings

## Decision features

Recommended:
- price-change prediction
- ownership/EO
- Free Hit logic
- Bench Boost logic
- differential mode

## Validation

Backtest:
- player point predictions
- expected minutes
- optimizer decisions
- captaincy
- transfer strategy
- chip strategy

## Project hygiene

Recommended:
- move V1–V5 into legacy/reference
- requirements.txt
- concise setup README
- unit tests for optimizer constraints
- one weekly runner

The full original review PDF is included beside this file.
