
import pandas as pd

from optimizer.starting_xi import select_starting_xi


def make_squad():
    rows = [
        # GK
        {"player_id": 1, "name": "GK A", "position": "GK", "team": "A", "price": 5.0, "predicted_points": 5.0},
        {"player_id": 2, "name": "GK B", "position": "GK", "team": "B", "price": 4.5, "predicted_points": 3.0},
        # DEF
        {"player_id": 3, "name": "DEF 1", "position": "DEF", "team": "A", "price": 5.0, "predicted_points": 8.0},
        {"player_id": 4, "name": "DEF 2", "position": "DEF", "team": "B", "price": 5.0, "predicted_points": 7.0},
        {"player_id": 5, "name": "DEF 3", "position": "DEF", "team": "C", "price": 5.0, "predicted_points": 6.0},
        {"player_id": 6, "name": "DEF 4", "position": "DEF", "team": "D", "price": 5.0, "predicted_points": 5.0},
        {"player_id": 7, "name": "DEF 5", "position": "DEF", "team": "E", "price": 5.0, "predicted_points": 4.0},
        # MID
        {"player_id": 8, "name": "MID 1", "position": "MID", "team": "F", "price": 5.0, "predicted_points": 9.0},
        {"player_id": 9, "name": "MID 2", "position": "MID", "team": "G", "price": 5.0, "predicted_points": 8.0},
        {"player_id": 10, "name": "MID 3", "position": "MID", "team": "H", "price": 5.0, "predicted_points": 7.0},
        {"player_id": 11, "name": "MID 4", "position": "MID", "team": "I", "price": 5.0, "predicted_points": 6.0},
        {"player_id": 12, "name": "MID 5", "position": "MID", "team": "J", "price": 5.0, "predicted_points": 5.0},
        # FWD
        {"player_id": 13, "name": "FWD 1", "position": "FWD", "team": "K", "price": 5.0, "predicted_points": 10.0},
        {"player_id": 14, "name": "FWD 2", "position": "FWD", "team": "L", "price": 5.0, "predicted_points": 9.0},
        {"player_id": 15, "name": "FWD 3", "position": "FWD", "team": "M", "price": 5.0, "predicted_points": 8.0},
    ]
    return pd.DataFrame(rows)


def test_select_starting_xi_returns_valid_formation():
    result = select_starting_xi(make_squad())

    assert len(result["starting_xi"]) == 11
    assert len(result["bench"]) == 4

    xi = pd.DataFrame(result["starting_xi"])
    assert (xi["position"] == "GK").sum() == 1
    assert 3 <= (xi["position"] == "DEF").sum() <= 5
    assert 2 <= (xi["position"] == "MID").sum() <= 5
    assert 1 <= (xi["position"] == "FWD").sum() <= 3


def test_select_starting_xi_maximizes_predicted_points():
    result = select_starting_xi(make_squad())

    xi_names = {p["name"] for p in result["starting_xi"]}

    # Best legal formation is 3-4-3 for this fixture.
    assert xi_names == {
        "GK A",
        "DEF 1", "DEF 2", "DEF 3",
        "MID 1", "MID 2", "MID 3", "MID 4",
        "FWD 1", "FWD 2", "FWD 3",
    }


def test_captain_and_vice_are_highest_predicted_xi_players():
    result = select_starting_xi(make_squad())

    assert result["captain"]["name"] == "FWD 1"
    assert result["vice_captain"]["name"] == "MID 1"


def test_bench_contains_unused_players_and_bench_gk():
    result = select_starting_xi(make_squad())

    bench_names = [p["name"] for p in result["bench"]]

    assert "GK B" in bench_names
    assert set(bench_names) == {"GK B", "DEF 4", "DEF 5", "FWD 2"} or set(bench_names) == {
        "GK B", "DEF 4", "DEF 5", "MID 5"
    }


def test_select_starting_xi_rejects_invalid_squad():
    squad = make_squad().drop(index=0)

    import pytest
    with pytest.raises(ValueError, match="exactly 15"):
        select_starting_xi(squad)


def test_formation_matches_returned_xi_counts():
    result = select_starting_xi(make_squad())
    defenders, midfielders, forwards = map(int, result["formation"].split("-"))
    xi = pd.DataFrame(result["starting_xi"])

    assert (xi["position"] == "DEF").sum() == defenders
    assert (xi["position"] == "MID").sum() == midfielders
    assert (xi["position"] == "FWD").sum() == forwards


def test_starting_xi_and_bench_partition_the_15_player_squad():
    result = select_starting_xi(make_squad())
    xi_ids = {p["player_id"] for p in result["starting_xi"]}
    bench_ids = {p["player_id"] for p in result["bench"]}

    assert len(xi_ids) == 11
    assert len(bench_ids) == 4
    assert xi_ids.isdisjoint(bench_ids)
    assert xi_ids | bench_ids == set(make_squad()["player_id"])


def test_captain_and_vice_are_in_starting_xi_and_unique():
    result = select_starting_xi(make_squad())
    xi_ids = {p["player_id"] for p in result["starting_xi"]}

    assert result["captain"]["player_id"] in xi_ids
    assert result["vice_captain"]["player_id"] in xi_ids
    assert result["captain"]["player_id"] != result["vice_captain"]["player_id"]


def test_doubtful_player_starts_when_his_substitute_covers_him():
    # MID 4: 8 points if he plays, 60% chance, so 4.8 expected: below the
    # healthy 5-point bench players on his own. But when he misses, a 5-point
    # substitute comes on, so starting him is worth 4.8 + 0.4 * 5 = 6.8.
    squad = make_squad()
    squad["availability_multiplier"] = 1.0
    squad.loc[squad["player_id"] == 11, ["predicted_points", "availability_multiplier"]] = [4.8, 0.6]

    result = select_starting_xi(squad)

    assert "MID 4" in {p["name"] for p in result["starting_xi"]}
    assert result["bench"][0]["predicted_points"] == 5.0
    # Reported points stay the plain expected points.
    assert result["starting_xi_base_points"] == sum(p["predicted_points"] for p in result["starting_xi"])


def test_without_availability_data_the_plain_ranking_is_used():
    squad = make_squad()
    squad.loc[squad["player_id"] == 11, "predicted_points"] = 4.8

    result = select_starting_xi(squad)

    assert "MID 4" not in {p["name"] for p in result["starting_xi"]}


def test_ruled_out_player_is_benched_not_covered():
    squad = make_squad()
    squad["availability_multiplier"] = 1.0
    squad.loc[squad["player_id"] == 11, ["predicted_points", "availability_multiplier"]] = [0.0, 0.0]

    result = select_starting_xi(squad)

    assert "MID 4" not in {p["name"] for p in result["starting_xi"]}
