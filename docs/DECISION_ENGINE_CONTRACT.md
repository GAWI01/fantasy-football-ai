# FPL-AI Decision Engine Contract

## Purpose

This document defines the target interface for the FPL-AI decision engine.

The decision engine is the layer above the existing prediction and squad-optimization components. It must turn a user's current FPL state plus model predictions into a structured, deterministic decision result that the frontend can consume.

The contract is intentionally defined before implementation so that individual modules can be built independently without creating incompatible interfaces.

---

## 1. Current verified foundation

The existing `optimizer/squad_optimizer.py` is the current squad-selection core.

Verified behavior:

- accepts a pandas DataFrame
- required fields:
  - `name`
  - `position`
  - `team`
  - `price`
  - `predicted_points`
- normalizes `GKP` to `GK`
- selects exactly 15 players
- enforces:
  - 2 GK
  - 5 DEF
  - 5 MID
  - 3 FWD
  - maximum 3 players per club
  - total cost <= supplied budget
- uses `scipy.optimize.milp`
- can consume the real `gw2_predictions_v5.csv` dataset
- real-data audit produced a valid 15-player squad at 99.7m with 62.779 predicted points
- measured optimizer runtime was approximately 0.038 seconds on the audit environment

The existing optimizer is therefore preserved as the squad-selection core.

---

## 2. Target decision pipeline

```text
FPL API / current data
        |
        v
Current Team
        |
        +----------------------+
        |                      |
        v                      v
Predictions              Fixtures / Context
        |                      |
        +----------+-----------+
                   |
                   v
            Squad Optimizer
                   |
                   v
             Optimal Squad
                   |
                   v
            Decision Engine
          /       |                 v        v         v
       XI      Captain    Transfers
         |        |         |
         +--------+---------+
                  |
                  v
          Structured Decision
                  |
                  v
             API / Frontend
```

---

## 3. Decision request

Conceptual request:

```json
{
  "team_id": 6658075,
  "gameweek": 3,
  "mode": "standard",
  "horizon": 5
}
```

### Required request fields

- `team_id`: positive FPL team ID

### Optional request fields

- `gameweek`: target decision gameweek
- `mode`: strategy mode
- `horizon`: number of future gameweeks considered
- strategy/chip settings when those features exist

The API layer is responsible for obtaining current team data and predictions. The decision engine should consume normalized data rather than perform raw HTTP calls itself.

---

## 4. Current team model

The existing team service already provides:

- team_id
- name
- bank
- event
- transfers
- overall_rank
- event_points
- event_rank
- total_points
- value
- picks

Each pick can contain:

- player_id
- FPL position
- multiplier
- captain flag
- vice-captain flag
- enriched name
- position name
- club
- price
- status
- prediction

The decision engine must preserve the original FPL player IDs as the canonical identity.

---

## 5. Prediction model

The existing prediction CSV currently contains fields including:

- player_id
- name
- position
- team
- price
- opponent
- home
- difficulty
- form
- minutes
- xP
- availability
- ml_prediction
- predicted_points
- value

The target decision model may later add:

- predicted_points by gameweek
- xMins
- start_probability
- rotation_risk
- uncertainty
- ownership / effective ownership
- role metrics
- point-route metrics

Not every analytical field should automatically become an optimizer objective term. Backtesting must determine whether a signal belongs in prediction, uncertainty, optimization, or explanation.

---

# 6. Decision result

The target result is:

```json
{
  "meta": {},
  "current_team": {},
  "optimal_squad": {},
  "starting_xi": {},
  "bench": {},
  "captain": {},
  "vice_captain": {},
  "transfers": {},
  "alternatives": [],
  "projection": {},
  "risk": {},
  "explanation": {}
}
```

The result must be structured and machine-readable.

No frontend component should need to reconstruct FPL decision logic from raw player rows.

---

## 7. Current team

```json
{
  "team_id": 6658075,
  "name": "Example FC",
  "gameweek": 3,
  "bank": 5,
  "team_value": 1000,
  "overall_rank": 123456,
  "event_rank": 50000,
  "total_points": 150,
  "transfers": 1,
  "players": []
}
```

Values must originate from FPL/team data. Do not invent missing values.

---

## 8. Optimal squad

The squad optimizer returns the optimal 15-player selection under its current constraints.

Target representation:

```json
{
  "players": [],
  "total_cost": 99.7,
  "projected_points": 62.779,
  "constraints": {
    "squad_size": 15,
    "gk": 2,
    "def": 5,
    "mid": 5,
    "fwd": 3,
    "max_per_club": 3
  }
}
```

`projected_points` must be derived from the actual selected players, not hardcoded.

---

# 9. Starting XI

The decision layer must select a legal FPL starting XI from the 15-player squad.

Required output:

```json
{
  "formation": "3-4-3",
  "players": [],
  "projected_points": 0
}
```

Rules:

- exactly 11 starters
- exactly 1 goalkeeper
- legal FPL outfield formation
- remaining 4 players become bench
- selection should be based on the decision objective, not simply top 11 rows
- all selected players must belong to the optimized/current squad being evaluated

The implementation must support formation comparison rather than hardcoding one formation.

---

# 10. Bench

Required output:

```json
{
  "players": [
    {
      "player_id": 1,
      "bench_order": 1
    }
  ]
}
```

Rules:

- exactly 4 bench players
- bench goalkeeper must remain the goalkeeper bench option
- outfield bench order must be deterministic
- bench ordering should eventually consider expected minutes and substitution value

---

# 11. Captain and vice-captain

Required output:

```json
{
  "captain": {
    "player_id": 123,
    "projected_points": 8.4
  },
  "vice_captain": {
    "player_id": 456,
    "projected_points": 7.9
  }
}
```

Rules:

- captain must be in the starting XI
- vice-captain must be in the starting XI
- captain and vice-captain must be different players
- captain selection must use the same prediction/decision data as the XI
- captain multiplier must be represented correctly in total projected XI points
- later versions may incorporate ceiling, minutes risk, ownership and other captain-specific signals

---

# 12. Transfers

The transfer engine must evaluate the user's actual current squad rather than independently recommending unrelated players.

Target:

```json
{
  "recommended": [],
  "free_transfers": 1,
  "transfers_used": 1,
  "hit_cost": 0,
  "gross_gain": 3.8,
  "net_gain": 3.8
}
```

Each recommended transfer:

```json
{
  "player_out_id": 123,
  "player_out": "Player A",
  "player_in_id": 456,
  "player_in": "Player B",
  "predicted_gain": 3.8
}
```

---

## 13. Transfer constraints

The final transfer engine must enforce actual FPL squad constraints, including:

- 15-player squad validity
- position counts
- maximum 3 players from a club
- player availability
- transfer affordability
- current team value/bank
- transfer count
- free-transfer allowance
- hit cost
- duplicate-player prevention

The current `transfer_analysis.py` does not yet implement the complete constraint system.

Its current analysis:

- ranks owned players by transfer-out score
- finds same-position transfer-in candidates
- calculates predicted gain
- supports simple candidate budget filtering
- has a multi-transfer analysis helper

This is useful reusable groundwork, but it is **not yet the final transfer decision engine**.

---

# 14. Net gain

The final decision engine must distinguish:

```text
gross expected gain
-
transfer hit cost
=
net expected gain
```

For multi-gameweek decisions, this may later become:

```text
future expected points gained
-
transfer costs
-
opportunity cost
=
net decision value
```

The exact multi-GW objective must be validated through backtesting.

---

# 15. Alternatives

The engine should return alternatives rather than only one answer.

Example:

```json
{
  "alternatives": [
    {
      "type": "transfer",
      "player_out": "A",
      "player_in": "B",
      "net_gain": 3.8
    },
    {
      "type": "transfer",
      "player_out": "A",
      "player_in": "C",
      "net_gain": 3.2
    }
  ]
}
```

Alternatives must be real feasible alternatives, not generated text.

---

# 16. Projection

The projection section should eventually contain:

```json
{
  "gw1": 62.7,
  "gw2": 59.8,
  "gw3": 57.1,
  "gw4": 55.4,
  "gw5": 53.2
}
```

The system should support a multi-gameweek horizon.

Future gameweeks should not simply be treated as identical copies of GW+1.

---

# 17. Risk

Target structure:

```json
{
  "overall": 0.0,
  "minutes_risk": 0.0,
  "rotation_risk": 0.0,
  "availability_risk": 0.0,
  "uncertainty": 0.0
}
```

Risk values must eventually be derived from actual model signals.

Do not create arbitrary confidence percentages for the UI.

---

# 18. Explanation

The AI/UI explanation layer should receive structured facts.

Example:

```json
{
  "summary": "Transfer B is preferred.",
  "reasons": [
    "Higher predicted points",
    "Better upcoming fixtures",
    "Higher expected minutes"
  ],
  "risks": [
    "Rotation uncertainty"
  ]
}
```

The explanation layer must not invent underlying statistics.

---

# 19. Decision modes

Target modes:

### Standard
Optimize for expected points and normal FPL decision-making.

### Aggressive
Allow greater tolerance for variance/differentials where supported by the model.

### Conservative
Favor stability, minutes and lower uncertainty.

### Wildcard
First decide whether Wildcard use has sufficient marginal value, then optimize a multi-GW squad.

### Free Hit
Optimize a one-GW temporary squad.

### Bench Boost
Optimize squad depth and bench expected output.

### Triple Captain
Optimize captain expected value.

These modes are future capabilities and are not currently implemented as one unified system.

---

# 20. API boundary

The decision engine should be independent from FastAPI.

Preferred separation:

```text
backend/
    services/
    decision/
    schemas/
    main.py
```

FastAPI should:

1. validate request
2. obtain current data
3. invoke decision engine
4. serialize structured result
5. return JSON

The decision engine should not depend on HTTP request objects.

---

# 21. Determinism

For identical inputs and configuration:

- output must be deterministic
- player ordering must be deterministic
- alternatives must be deterministic
- tie-breaking must be deterministic

This is important for testing, caching and SaaS reproducibility.

---

# 22. Implementation order

The implementation order is deliberately:

1. Contract / schemas
2. Starting XI + formation
3. Bench ordering
4. Captain / vice-captain
5. Current-team transfer engine
6. Free transfers / hit economics
7. Multi-transfer optimization
8. Multi-GW planning
9. Chip decisions
10. Explanation output
11. FastAPI decision endpoint
12. Frontend integration
13. Backtesting

Do not implement all of these in one task.

Each stage must have tests before production behavior is added.

---

# 23. Current status

| Capability | Status |
|---|---|
| Prediction CSV | Implemented |
| Prediction data loading | Implemented |
| FPL team retrieval | Implemented |
| Fixture service | Implemented |
| MILP squad optimizer | Implemented + verified |
| 15-player constraints | Implemented + verified |
| Starting XI | Not implemented |
| Formation optimization | Not implemented |
| Bench ordering | Not implemented |
| Captain optimization | Not implemented |
| Vice-captain optimization | Not implemented |
| Transfer-out analysis | Implemented |
| Transfer-in analysis | Implemented |
| Multi-transfer analysis | Implemented but incomplete |
| Free-transfer economics | Not implemented |
| Hit economics | Not implemented |
| Full current-squad transfer optimization | Not implemented |
| Multi-GW optimization | Not implemented |
| Chip decision engine | Not implemented |
| Unified decision result | Not implemented |
| Decision API endpoint | Not implemented |
| UI integration of decision result | Not implemented |
| Backtesting | Not implemented |

---

# 24. Non-negotiable principles

1. Do not replace the working MILP optimizer without evidence that it is inadequate.
2. Do not hardcode analytical values for visual purposes.
3. Do not let frontend code become the decision engine.
4. Do not let the AI layer invent model statistics.
5. Every decision must be traceable to structured inputs.
6. FPL constraints must be enforced by backend logic.
7. Use tests before implementing new decision behavior.
8. Keep data preparation separate from combinatorial optimization.
9. Prefer deterministic outputs.
10. Backtest decision changes before tuning weights.
11. Do not add analytical signals to the objective simply because they are available.
12. Preserve player IDs as the canonical identity across all layers.

---

## 25. Definition of a complete decision

The decision engine is considered functionally complete for the standard mode only when it can take:

```text
real FPL team
+
real prediction data
+
real fixture/context data
```

and return:

```text
current squad
+
optimal feasible squad
+
legal starting XI
+
formation
+
bench order
+
captain
+
vice captain
+
feasible transfer recommendation
+
free-transfer/hit calculation
+
net expected gain
+
alternatives
+
structured explanation facts
```

All outputs must be testable and traceable.
