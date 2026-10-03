from backend.live_service import derive_free_transfers


def test_rolls_unused_transfers_up_to_five():
    state = derive_free_transfers(
        target_event=6,
        started_event=1,
        transfers=[],
        chips=[],
    )

    assert state == {"free_transfers": 5, "known": True}


def test_counts_transfers_already_made_for_target_event():
    state = derive_free_transfers(
        target_event=4,
        started_event=1,
        transfers=[
            {"event": 2},
            {"event": 4},
            {"event": 4},
        ],
        chips=[],
    )

    # GW2: 1 used; GW3: 1 rolled; GW4: 2 available, both used.
    assert state == {"free_transfers": 0, "known": True}


def test_wildcard_consumes_new_weekly_transfer_but_preserves_bank():
    state = derive_free_transfers(
        target_event=5,
        started_event=1,
        transfers=[{"event": 4}, {"event": 4}, {"event": 4}],
        chips=[{"name": "wildcard", "event": 4}],
    )

    # Two were banked before GW4; wildcard consumes that week's new transfer,
    # then GW5 adds one while the two banked transfers remain.
    assert state == {"free_transfers": 3, "known": True}


def test_first_deadline_has_unlimited_transfers():
    state = derive_free_transfers(
        target_event=1,
        started_event=1,
        transfers=[],
        chips=[],
    )

    assert state == {"free_transfers": 20, "known": True}


def test_hits_do_not_carry_into_next_gameweek():
    # Team 6658075 in 2026/27: BB GW2, wildcard GW3, -4 in GW4, -20 in GW5.
    state = derive_free_transfers(
        target_event=6,
        started_event=1,
        transfers=[{"event": 2}] + [{"event": 3}] * 41 + [{"event": 4}] * 2 + [{"event": 5}] * 6,
        chips=[{"name": "bboost", "event": 2}, {"name": "wildcard", "event": 3}, {"name": "3xc", "event": 4}],
    )

    assert state == {"free_transfers": 1, "known": True}
