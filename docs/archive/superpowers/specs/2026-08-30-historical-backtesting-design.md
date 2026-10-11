# Historical Backtesting Engine — Design

The engine evaluates next-Gameweek predictions using only information available at the decision Gameweek. For decision GW G, the target is strictly GW G+1. The production prediction implementation is injected through a predictor adapter rather than duplicated. Results are player-level and reports are deterministic CSV/JSON artifacts.

Hard constraints: no future rows may reach the predictor; duplicate player predictions fail; missing targets/prediction fields fail; the first implementation does not fabricate historical manager squads or transfer decisions without real historical team snapshots.
