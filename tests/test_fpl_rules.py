from engine.fpl_rules import validate_transfer_squad


def make_player(player_id, team):
    return {
        "player_id": player_id,
        "team": team,
    }


def test_rejects_four_players_from_same_club_after_normal_transfer():
    current_squad = [
        make_player(1, "Man City"),
        make_player(2, "Man City"),
        make_player(3, "Man City"),
        make_player(4, "Everton"),
    ]

    resulting_squad = [
        make_player(1, "Man City"),
        make_player(2, "Man City"),
        make_player(3, "Man City"),
        make_player(5, "Man City"),
    ]

    assert validate_transfer_squad(
        current_squad=current_squad,
        resulting_squad=resulting_squad,
        transfer_context={
            "type": "normal_transfer",
            "out_player_id": 4,
            "in_player_id": 5,
        },
    ) is False


def test_allows_four_players_when_existing_player_changes_club():
    current_squad = [
        make_player(1, "Man City"),
        make_player(2, "Man City"),
        make_player(3, "Man City"),
        make_player(4, "Everton"),
    ]

    resulting_squad = [
        make_player(1, "Man City"),
        make_player(2, "Man City"),
        make_player(3, "Man City"),
        make_player(4, "Man City"),
    ]

    assert validate_transfer_squad(
        current_squad=current_squad,
        resulting_squad=resulting_squad,
        transfer_context={
            "type": "club_change",
            "player_id": 4,
            "old_club": "Everton",
            "new_club": "Man City",
        },
    ) is True

def test_rejects_fake_club_change_context():
    current_squad = [
        make_player(1, "Man City"),
        make_player(2, "Man City"),
        make_player(3, "Man City"),
        make_player(4, "Everton"),
    ]

    resulting_squad = [
        make_player(1, "Man City"),
        make_player(2, "Man City"),
        make_player(3, "Man City"),
        make_player(5, "Man City"),
    ]

    assert validate_transfer_squad(
        current_squad=current_squad,
        resulting_squad=resulting_squad,
        transfer_context={
            "type": "club_change",
            "player_id": 5,
            "old_club": "Everton",
            "new_club": "Man City",
        },
    ) is False

def test_normal_transfer_plan_cannot_create_four_from_same_club():
    current_squad = [
        make_player(1, "Man City"),
        make_player(2, "Man City"),
        make_player(3, "Man City"),
        make_player(4, "Everton"),
    ]

    resulting_squad = [
        make_player(1, "Man City"),
        make_player(2, "Man City"),
        make_player(3, "Man City"),
        make_player(5, "Man City"),
    ]

    assert validate_transfer_squad(
        current_squad=current_squad,
        resulting_squad=resulting_squad,
        transfer_context={
            "type": "normal_transfer",
            "out_player_id": 4,
            "in_player_id": 5,
        },
    ) is False

def test_detect_club_changes_finds_owned_player_who_changed_club():
    from engine.fpl_rules import detect_club_changes

    current_squad = [
        {"player_id": 4},
        {"player_id": 5},
    ]

    previous_predictions = [
        {"player_id": 4, "team": "Everton"},
        {"player_id": 5, "team": "Arsenal"},
    ]

    current_predictions = [
        {"player_id": 4, "team": "Man City"},
        {"player_id": 5, "team": "Arsenal"},
    ]

    changes = detect_club_changes(
        current_squad=current_squad,
        previous_predictions=previous_predictions,
        current_predictions=current_predictions,
    )

    assert changes == [
        {
            "player_id": 4,
            "old_club": "Everton",
            "new_club": "Man City",
        }
    ]
