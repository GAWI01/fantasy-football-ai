from __future__ import annotations

from itertools import product

import pandas as pd


POSITION_COUNTS = {
    "GK": 2,
    "DEF": 5,
    "MID": 5,
    "FWD": 3,
}

# Legal FPL outfield formations. Each tuple is DEF, MID, FWD.
LEGAL_FORMATIONS = tuple(
    (defenders, midfielders, forwards)
    for defenders in range(3, 6)
    for midfielders in range(2, 6)
    for forwards in range(1, 4)
    if defenders + midfielders + forwards == 10
)


class StartingXIError(ValueError):
    """Raised when a starting XI cannot be created."""


def _normalize_positions(squad: pd.DataFrame) -> pd.DataFrame:
    result = squad.copy()
    result["position"] = (
        result["position"]
        .astype(str)
        .str.strip()
        .str.upper()
        .replace({"GKP": "GK"})
    )
    return result


def _validate_squad(squad: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(squad, pd.DataFrame):
        raise StartingXIError("squad must be a pandas DataFrame")

    required = {"player_id", "name", "position", "predicted_points"}
    missing = required - set(squad.columns)
    if missing:
        raise StartingXIError(
            "squad is missing required columns: "
            + ", ".join(sorted(missing))
        )

    if len(squad) != 15:
        raise StartingXIError("squad must contain exactly 15 players")

    result = _normalize_positions(squad)
    result["predicted_points"] = pd.to_numeric(
        result["predicted_points"],
        errors="coerce",
    )

    if result["predicted_points"].isna().any():
        raise StartingXIError(
            "squad contains invalid predicted_points"
        )

    if result["player_id"].duplicated().any():
        raise StartingXIError("squad contains duplicate player IDs")

    counts = result["position"].value_counts().to_dict()
    expected = dict(POSITION_COUNTS)

    if counts != expected:
        raise StartingXIError(
            "squad must contain exactly 2 GK, 5 DEF, 5 MID and 3 FWD"
        )

    return result


def _rank_players(players: pd.DataFrame, column: str = "predicted_points") -> pd.DataFrame:
    return players.sort_values(
        [column, "player_id"],
        ascending=[False, True],
        kind="mergesort",
    )


def doubt_share(squad: pd.DataFrame) -> pd.Series:
    """Chance each player misses the Gameweek, for doubtful players only.

    `availability_multiplier` is the official chance of playing (already
    folded into `predicted_points`). Only a doubtful player (0 < chance < 1)
    counts: a ruled-out player is simply benched, and a fit player's ordinary
    rotation risk is not part of this.
    """
    if "availability_multiplier" not in squad.columns:
        return pd.Series(0.0, index=squad.index)
    chance = pd.to_numeric(squad["availability_multiplier"], errors="coerce").fillna(1.0)
    return (1.0 - chance).where((chance > 0) & (chance < 1), 0.0)


def _select_for_formation(
    squad: pd.DataFrame,
    formation: tuple[int, int, int],
) -> pd.DataFrame:
    defenders, midfielders, forwards = formation

    selected_parts = []

    for position, count in (
        ("GK", 1),
        ("DEF", defenders),
        ("MID", midfielders),
        ("FWD", forwards),
    ):
        players = _rank_players(
            squad[squad["position"] == position],
            "_rank_points",
        )
        selected_parts.append(players.head(count))

    return pd.concat(selected_parts, ignore_index=True)


def _player_records(players: pd.DataFrame) -> list[dict]:
    records = []
    for _, row in players.iterrows():
        record = row.to_dict()
        if isinstance(record.get("predicted_points"), float):
            record["predicted_points"] = float(record["predicted_points"])
        records.append(record)
    return records


def _cover_points(squad: pd.DataFrame, bench: pd.DataFrame) -> pd.Series:
    """Points of the substitute who would replace each player: the best bench
    player of the same kind (outfield or goalkeeper), never the player himself."""
    values = []
    for index, row in squad.iterrows():
        keeper = row["position"] == "GK"
        others = bench[((bench["position"] == "GK") == keeper) & (bench["player_id"] != row["player_id"])]
        values.append(float(others["predicted_points"].max()) if len(others) else 0.0)
    return pd.Series(values, index=squad.index)


def _best_formation(squad: pd.DataFrame) -> dict:
    best = None
    for formation in LEGAL_FORMATIONS:
        xi = _select_for_formation(squad, formation)
        points = float(xi["_rank_points"].sum())
        key = (
            points,
            formation[0],
            formation[1],
            tuple(sorted(int(player_id) for player_id in xi["player_id"])),
        )
        if best is None or key > best["key"]:
            best = {"key": key, "formation": formation, "starting_xi": xi}
    assert best is not None
    return best


def select_starting_xi(squad: pd.DataFrame) -> dict:
    """
    Select the highest-predicted legal starting XI from a valid 15-player squad.

    Every legal FPL outfield formation is evaluated. For each formation,
    the highest predicted player(s) at each position are selected. The
    formation with the highest total predicted points wins.

    Tie-breaking:
    - formation with more defenders first
    - then more midfielders
    - then deterministic player ordering

    Bench order:
    - best remaining outfield player first
    - remaining outfield players by predicted points
    - bench goalkeeper last

    Captain and vice-captain:
    - highest predicted-point starter becomes captain
    - second-highest becomes vice-captain
    - player_id breaks ties deterministically
    """
    squad = _validate_squad(squad)

    # A doubtful starter is covered by the bench: when he misses, FPL brings on
    # the first substitute who fits. So a starter is worth his own expected
    # points plus his chance of missing times the points of the player who
    # would come on. That substitute depends on the XI, so the XI is chosen
    # again with the cover of the previous choice until it settles.
    doubt = doubt_share(squad)
    squad = squad.assign(_rank_points=squad["predicted_points"])
    best = None
    for _ in range(3):
        best = _best_formation(squad)
        bench = squad[~squad["player_id"].isin(set(best["starting_xi"]["player_id"]))]
        ranked = squad["predicted_points"] + doubt * _cover_points(squad, bench)
        if not doubt.any() or ranked.equals(squad["_rank_points"]):
            break
        squad = squad.assign(_rank_points=ranked)

    assert best is not None

    xi = best["starting_xi"].drop(columns="_rank_points")
    xi = xi.sort_values(
        ["position", "predicted_points", "player_id"],
        ascending=[True, False, True],
        kind="mergesort",
    ).reset_index(drop=True)

    xi_ids = set(xi["player_id"])
    remaining = squad[~squad["player_id"].isin(xi_ids)].drop(columns="_rank_points")

    bench_outfield = _rank_players(
        remaining[remaining["position"] != "GK"]
    )
    bench_goalkeeper = remaining[remaining["position"] == "GK"]

    bench = pd.concat(
        [bench_outfield, bench_goalkeeper],
        ignore_index=True,
    ).reset_index(drop=True)

    xi_ranked = _rank_players(xi)

    captain_row = xi_ranked.iloc[0]
    vice_row = xi_ranked.iloc[1]

    base_points = float(xi["predicted_points"].sum())
    captain_points = float(captain_row["predicted_points"])

    return {
        "formation": (
            f"{best['formation'][0]}-"
            f"{best['formation'][1]}-"
            f"{best['formation'][2]}"
        ),
        "starting_xi": _player_records(xi),
        "bench": [
            {
                **record,
                "bench_order": index,
            }
            for index, record in enumerate(
                _player_records(bench),
                start=1,
            )
        ],
        "captain": _player_records(
            pd.DataFrame([captain_row])
        )[0],
        "vice_captain": _player_records(
            pd.DataFrame([vice_row])
        )[0],
        "projected_points": base_points + captain_points,
        "starting_xi_base_points": base_points,
    }
