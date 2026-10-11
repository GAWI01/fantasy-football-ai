# Frontend integration — Backend live-data foundation

## Part 1 scope

This package adds the backend contracts required by the upcoming dashboard integration.

### New endpoints

- `GET /live/players?limit=20&position=MID`
  - Reads the current FPL Gameweek from `bootstrap-static/`.
  - Reads `/event/{gw}/live/`.
  - Returns actual Gameweek points, minutes, goals, assists, bonus, BPS, form, ownership and basic player metadata.
- `GET /team/{team_id}/live`
  - Combines the manager's current picks with actual current-GW player points.
  - Returns captain multiplier and multiplied live points.
- `GET /team/{team_id}/history`
  - Returns normalized Gameweek history for rank/points trend charts.
- `GET /fixtures/team/{team_id}/upcoming?limit=10`
  - Returns upcoming matches across multiple Gameweeks.
  - Each fixture is represented once as `home_team` vs `away_team`.
  - Ordered chronologically.
  - Includes overall fixture difficulty and home/away difficulty.

The existing `/fixtures/team/{team_id}` contract is retained for compatibility.

## Verification

Backend tests cover:
- live player normalization and ranking
- current/finished Gameweek status
- team history normalization
- live squad point/multiplier merging
- chronological multi-GW fixtures
- existing team/fixture/decision API regression

The audit runtime cannot reach external FPL endpoints because outbound DNS/network access is unavailable. The live HTTP integration itself must therefore be smoke-tested on the user's local machine.
