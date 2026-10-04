import unittest

from feature_contract import (
    FEATURE_COLUMNS,
    FeatureContractError,
    build_feature_row,
    validate_model_feature_names,
)


class FeatureContractTests(unittest.TestCase):
    def test_builds_training_and_live_rows_in_the_identical_order(self) -> None:
        raw = {
            "price": "7.5", "was_home": True, "points_last_3": 8,
            "points_last_5": 11, "points_avg_5": 2.2,
            "minutes_last_5": 360, "starts_last_5": 4,
            "goals_last_5": 1, "assists_last_5": 2, "bps_avg_5": 18,
            "influence_avg_5": 22, "creativity_avg_5": 15,
            "threat_avg_5": 30, "ict_index_avg_5": 6.7,
            "fixture_difficulty": 3, "position": "MID",
        }

        training = build_feature_row(raw)
        live = build_feature_row(dict(raw))

        self.assertEqual(list(FEATURE_COLUMNS), list(training))
        self.assertEqual(training, live)

    def test_rejects_missing_required_feature(self) -> None:
        with self.assertRaisesRegex(FeatureContractError, "minutes_last_5"):
            build_feature_row({"position": "MID"})

    def test_rejects_a_persisted_model_with_drifted_features(self) -> None:
        with self.assertRaisesRegex(FeatureContractError, "retrain required"):
            validate_model_feature_names(["price", "legacy_feature"])


if __name__ == "__main__":
    unittest.main()
