import pandas as pd

from engine.transfer_analysis import price_swaps


def _frame(rows):
    return pd.DataFrame(rows, columns=["player_id", "name", "position", "team", "price", "predicted_points"])


def _squad():
    rows = []
    pid = 1
    for position, count, points in (("GK", 2, 3.0), ("DEF", 5, 3.0), ("MID", 5, 4.0), ("FWD", 3, 4.0)):
        for index in range(count):
            rows.append([pid, f"{position}{index}", position, f"Club{pid}", 5.0, points])
            pid += 1
    return rows


def _team(rows):
    return {"bank": 1.0, "picks": [{"player_id": row[0], "position": index + 1, "purchase_price": 5.0, "selling_price": 5.0}
                                   for index, row in enumerate(rows)]}


def test_suggests_a_riser_that_keeps_points_and_skips_one_that_loses_them():
    rows = _squad()
    rows.append([100, "Riser", "MID", "Club100", 5.5, 4.6])   # better and likely to rise
    rows.append([101, "WeakRiser", "MID", "Club101", 5.5, 1.0])  # likely to rise but far worse
    frame = _frame(rows)
    result = price_swaps(_team(rows[:15]), frame, likelihoods={100: 5, 101: 5, 8: -4}, free_transfers=1,
                         horizon_predictions=[frame, frame], horizon_weights=[1.0, 0.9])
    names = [swap["player_in"] for swap in result["swaps"]]
    assert "Riser" in names
    assert "WeakRiser" not in names
    best = result["swaps"][0]
    assert best["projected_net_gain"] >= -0.5
    assert best["in_likelihood"] == 5
    assert result["owned_fallers"] == [{"player_id": 8, "name": "MID0", "likelihood": -4}]
    # Each incoming player appears once.
    assert len({swap["player_in_id"] for swap in result["swaps"]}) == len(result["swaps"])


def test_no_risers_means_no_swaps():
    rows = _squad()
    frame = _frame(rows)
    result = price_swaps(_team(rows), frame, likelihoods={}, free_transfers=1)
    assert result["swaps"] == []
    assert result["risers_considered"] == 0
