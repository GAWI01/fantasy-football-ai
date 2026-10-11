from backend.selling_prices import DERIVED_SOURCE, attach_selling_prices, derive_purchase_prices, selling_price


def test_fpl_selling_price_rule():
    assert selling_price(7.0, 7.5) == 7.2   # half of +0.5, rounded down
    assert selling_price(7.0, 7.1) == 7.0   # +0.1 rise keeps nothing
    assert selling_price(7.0, 7.2) == 7.1
    assert selling_price(7.0, 6.7) == 6.7   # falls are passed on in full


ELEMENTS = [
    {"id": 1, "now_cost": 75, "cost_change_start": 5},   # started at 7.0
    {"id": 2, "now_cost": 60, "cost_change_start": 0},
    {"id": 3, "now_cost": 102, "cost_change_start": 2},
]


def test_latest_transfer_in_sets_the_purchase_price_and_free_hit_moves_are_ignored():
    transfers = [
        {"element_in": 2, "element_in_cost": 55, "event": 3, "time": "2026-09-04T10:00:00Z"},
        {"element_in": 2, "element_in_cost": 58, "event": 5, "time": "2026-09-18T10:00:00Z"},  # Free Hit
        {"element_in": 3, "element_in_cost": 100, "event": 4, "time": "2026-09-12T10:00:00Z"},
    ]
    chips = [{"name": "freehit", "event": 5}]
    prices = derive_purchase_prices([1, 2, 3], transfers=transfers, chips=chips, elements=ELEMENTS, started_event=1)
    assert prices == {1: 7.0, 2: 5.5, 3: 10.0}


def test_untraceable_purchase_keeps_the_estimate():
    picks = attach_selling_prices([{"player_id": 1}], transfers=[], chips=[], elements=ELEMENTS, started_event=4)
    assert "selling_price" not in picks[0]


def test_attached_prices_are_marked_as_derived_and_count_as_known():
    from engine.transfer_analysis import selling_value

    picks = attach_selling_prices([{"player_id": 1}], transfers=[], chips=[], elements=ELEMENTS, started_event=1)
    assert picks[0]["purchase_price"] == 7.0
    assert picks[0]["selling_price"] == 7.2
    assert picks[0]["selling_price_source"] == DERIVED_SOURCE
    value, source, known = selling_value(picks[0], 7.5)
    assert (value, source, known) == (7.2, DERIVED_SOURCE, True)
