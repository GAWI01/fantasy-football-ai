from engine.decision_strategy import (
    BENCH_BOOST_MIN_BENCH_POINTS,
    FREE_HIT_MIN_GAIN,
    chip_advisor,
    classify_action,
    decision_confidence,
)


def test_action_label_follows_the_chosen_transfer_count():
    assert classify_action(0, 0.0) == "HOLD"
    assert classify_action(1, 0.0) == "SINGLE_TRANSFER"
    assert classify_action(2, 0.0) == "MULTI_TRANSFER"
    assert classify_action(2, 4.0) == "HIT"


def test_confidence_is_high_only_when_margin_clearly_exceeds_uncertainty():
    chosen = {"decision_score": 6.0, "uncertainty": 2.0}
    assert decision_confidence(chosen, {"decision_score": 3.5, "uncertainty": 2.0})["label"] == "HIGH"
    assert decision_confidence(chosen, {"decision_score": 5.0, "uncertainty": 2.0})["label"] == "MEDIUM"
    assert decision_confidence(chosen, {"decision_score": 5.8, "uncertainty": 2.0})["label"] == "LOW"


def test_confidence_is_unknown_without_a_comparison_or_uncertainty():
    assert decision_confidence({"decision_score": 1.0}, None)["label"] == "UNKNOWN"
    assert decision_confidence({"decision_score": 1.0}, {"decision_score": 0.0})["label"] == "UNKNOWN"


def test_minutes_doubt_caps_confidence_below_high():
    result = decision_confidence(
        {"decision_score": 9.0, "uncertainty": 1.0}, {"decision_score": 0.0, "uncertainty": 1.0},
        minutes_doubts=["X starts with 50% probability"])
    assert result["label"] == "MEDIUM"


def test_available_chip_is_not_a_recommendation():
    advice = chip_advisor(wildcard_available=True, free_hit_available=True, bench_boost_available=True,
                          triple_captain_available=True)
    assert advice["recommended_chip"] is None


def test_wildcard_needs_planner_evidence():
    weak = chip_advisor(wildcard_available=True, wildcard_signal={"recommended": False, "advantage": 4.0})
    strong = chip_advisor(wildcard_available=True, wildcard_signal={"recommended": True, "advantage": 22.0, "threshold": 15.0})
    assert weak["recommended_chip"] is None
    assert strong["recommended_chip"] == "WILDCARD"


def test_free_hit_and_bench_boost_need_value_not_just_a_flag():
    blank = chip_advisor(free_hit_available=True, blank_gameweek=True, scenario_scores={"FREE_HIT": FREE_HIT_MIN_GAIN - 1})
    assert blank["recommended_chip"] is None
    blank = chip_advisor(free_hit_available=True, blank_gameweek=True, scenario_scores={"FREE_HIT": FREE_HIT_MIN_GAIN + 1})
    assert blank["recommended_chip"] == "FREE_HIT"
    double = chip_advisor(bench_boost_available=True, double_gameweek=True,
                          scenario_scores={"BENCH_BOOST": BENCH_BOOST_MIN_BENCH_POINTS - 0.5})
    assert double["recommended_chip"] is None
