import unittest

import numpy as np
import pandas as pd
import torch

from app import methods


class SequenceTests(unittest.TestCase):
    def test_build_sequences_uses_next_value_as_target(self):
        series = np.array([[1.0], [2.0], [3.0], [4.0]])

        features, targets = methods.build_sequences(series, seq_len=2)

        self.assertEqual(tuple(features.shape), (2, 2, 1))
        self.assertEqual(tuple(targets.shape), (2, 1))
        torch.testing.assert_close(features[0], torch.tensor([[1.0], [2.0]]))
        torch.testing.assert_close(targets[:, 0], torch.tensor([3.0, 4.0]))

    def test_split_preserves_time_order(self):
        features = torch.arange(10, dtype=torch.float32).reshape(5, 2)
        targets = torch.arange(5, dtype=torch.float32)

        train_x, train_y, test_x, test_y = methods.split(
            features, targets, train_ratio=0.6
        )

        self.assertEqual(len(train_x), 3)
        self.assertEqual(len(test_x), 2)
        torch.testing.assert_close(train_y, torch.tensor([0.0, 1.0, 2.0]))
        torch.testing.assert_close(test_y, torch.tensor([3.0, 4.0]))


class PreprocessTests(unittest.TestCase):
    def test_resamples_to_half_hour_and_interpolates_missing_rate(self):
        source = pd.DataFrame(
            {
                "Date": ["2026-08-11 10:00:00", "2026-08-11 11:00:00"],
                "Rate": [7.0, 8.0],
                "Currency": ["USD", "USD"],
            }
        )

        result = methods.preprocess(source)

        self.assertEqual(len(result), 3)
        self.assertEqual(result.index.freqstr, "30min")
        self.assertAlmostEqual(result.loc["2026-08-11 10:30:00", "Rate"], 7.5)


class MetricTests(unittest.TestCase):
    def test_evaluate_metrics_returns_expected_regression_metrics(self):
        result = methods.evaluate_metrics(
            np.array([1.0, 2.0]), np.array([1.0, 3.0]), verbose=False
        )

        self.assertAlmostEqual(result["mae"], 0.5)
        self.assertAlmostEqual(result["mse"], 0.5)
        self.assertAlmostEqual(result["rmse"], np.sqrt(0.5))
        self.assertAlmostEqual(result["mape"], 25.0)

    def test_mape_is_nan_when_all_actual_values_are_zero(self):
        result = methods.evaluate_metrics([0.0, 0.0], [1.0, 2.0], verbose=False)

        self.assertTrue(np.isnan(result["mape"]))


if __name__ == "__main__":
    unittest.main()
