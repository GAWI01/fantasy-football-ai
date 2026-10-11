# ARCHITECTURE.md

## Target architecture

```text
                 ┌──────────────────┐
                 │     FPL API      │
                 └────────┬─────────┘
                          ↓
                 ┌──────────────────┐
                 │   Data Ingestion │
                 └────────┬─────────┘
                          ↓
              ┌────────────────────────┐
              │ Historical + Current DB│
              └────────────┬───────────┘
                           ↓
                 ┌──────────────────┐
                 │ Feature Pipeline │
                 └────────┬─────────┘
                          ↓
          ┌──────────────────────────────┐
          │ Availability / xMins / Risk  │
          └──────────────┬───────────────┘
                         ↓
                 ┌──────────────────┐
                 │ Prediction Layer │
                 └────────┬─────────┘
                          ↓
       ┌────────────────────────────────────┐
       │ Fixtures / Roles / Point Routes / │
       │ Ownership / Uncertainty / Context │
       └────────────────┬───────────────────┘
                        ↓
              ┌─────────────────────┐
              │ Optimization Engine │
              │      MILP / ILP     │
              └──────────┬──────────┘
                         ↓
              ┌─────────────────────┐
              │ Structured JSON     │
              │ Weekly Decision Data│
              └──────────┬──────────┘
                         ↓
              ┌─────────────────────┐
              │ AI / ChatGPT Layer  │
              └─────────────────────┘
```

## Separation of responsibilities

### Data layer
Responsible for fetching, validating and storing source data.

### Feature layer
Responsible for transforming raw data into model features.

### Prediction layer
Responsible for expected output, expected minutes and uncertainty.

### Optimization layer
Responsible for decisions under FPL constraints.

### AI layer
Responsible for interpretation and decision discussion.

## Optimizer design

A player-selection variable can be binary:

`x_player ∈ {0,1}`

Core constraints:
- sum GKP = 2
- sum DEF = 5
- sum MID = 5
- sum FWD = 3
- total cost <= budget
- max 3 players from each club

Separate variables may be used for:
- starting XI
- captain
- vice-captain
- bench order
- transfer in/out

Objective should eventually combine:
- expected points
- multiple-GW value
- minutes confidence
- role/point-route information
- risk
- ownership/EO depending on strategy
- transfer/chip opportunity cost

The exact weights must be validated by backtesting.

## Performance requirement

Target:
- normal weekly optimization in seconds
- no giant positional-combination enumeration
- no DataFrame creation inside search loops
- full player pool should be feasible input

## Data contract

The optimizer should consume a clean table/object model with fields conceptually similar to:

- player_id
- name
- position
- team
- price
- predicted_points_gw1..gwn
- xmins_gw1..gwn
- start_probability
- availability
- rotation_risk
- uncertainty
- ownership
- role metrics
- point-route metrics

The output should contain:
- selected squad
- starting XI
- bench
- captain
- vice captain
- total cost
- projected points
- risk metrics
- rationale fields
- rejected/alternative candidates where useful

## Important principle

Do not force every analytical feature directly into the objective.

Some features should influence predictions, some should influence uncertainty, and some should be explanatory metadata.

Backtesting decides which signals actually improve decisions.
