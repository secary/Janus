import unittest
from unittest.mock import MagicMock, patch

import pandas as pd

from app import tune


class TunerRegistryTests(unittest.TestCase):
    def test_dispatches_currency_to_registered_tuner(self):
        tuner = MagicMock(return_value={"score": 1.0})
        with patch.dict(tune.TUNERS, {"example": tuner}, clear=True):
            result = tune.tune_currency("example", "USD")

        tuner.assert_called_once_with("USD")
        self.assertEqual(result, {"score": 1.0})

    def test_rejects_unknown_model(self):
        with self.assertRaisesRegex(ValueError, "Unsupported model"):
            tune.tune_currency("unknown", "USD")


class TuningOrchestrationTests(unittest.TestCase):
    def test_skips_currency_with_insufficient_history(self):
        tuner = MagicMock()
        with (
            patch.dict(tune.TUNERS, {"example": tuner}, clear=True),
            patch.object(tune, "CURRENCIES", ["美元"]),
            patch.object(tune, "get_currency_code", return_value="USD"),
            patch.object(
                tune, "fetch_history", return_value=pd.DataFrame(index=range(499))
            ),
        ):
            tune.main("example")
        tuner.assert_not_called()

    def test_tunes_each_currency_with_enough_history(self):
        tuner = MagicMock()
        with (
            patch.dict(tune.TUNERS, {"example": tuner}, clear=True),
            patch.object(tune, "CURRENCIES", ["美元"]),
            patch.object(tune, "get_currency_code", return_value="USD"),
            patch.object(
                tune, "fetch_history", return_value=pd.DataFrame(index=range(500))
            ),
        ):
            tune.main("example")
        tuner.assert_called_once_with("USD")


if __name__ == "__main__":
    unittest.main()
