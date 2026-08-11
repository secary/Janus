import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd


FORECAST_DIR = Path(__file__).resolve().parents[1] / "forecast"
sys.path.insert(0, str(FORECAST_DIR))

import Jervis  # noqa: E402


class LstmPredictTests(unittest.TestCase):
    def test_generates_half_hour_predictions_for_requested_days(self):
        index = pd.date_range("2026-08-10", periods=48, freq="30min")
        history = pd.DataFrame({"Rate": np.linspace(7.0, 7.47, 48)}, index=index)
        scaled = np.linspace(0.0, 1.0, 48).reshape(-1, 1)
        model = MagicMock()
        model.return_value.cpu.return_value.numpy.return_value = np.array([[0.5]])

        with (
            patch.object(Jervis, "load_latest_model", return_value=model),
            patch.object(Jervis, "fetch_history", return_value=pd.DataFrame()),
            patch.object(Jervis, "preprocess", return_value=history),
            patch.object(Jervis, "scale", side_effect=[scaled, np.full((48, 1), 7.25)]),
            patch.object(Jervis.torch.cuda, "is_available", return_value=False),
        ):
            result = Jervis.lstm_predict("usd", days=1)

        self.assertEqual(len(result), 48)
        self.assertTrue((result["Currency"] == "USD").all())
        self.assertTrue((result["Predicted_Rates"] == 7.25).all())
        self.assertEqual(result.iloc[0]["Date"], index[-1] + pd.Timedelta(minutes=30))
        self.assertEqual(result.iloc[-1]["Date"], index[-1] + pd.Timedelta(days=1))


class PredictionOrchestrationTests(unittest.TestCase):
    def test_main_skips_currency_when_history_is_insufficient(self):
        with (
            patch.object(Jervis, "CURRENCIES", ["美元"]),
            patch.object(Jervis, "get_currency_code", return_value="USD"),
            patch.object(Jervis, "fetch_history", return_value=pd.DataFrame(index=range(499))),
            patch.object(Jervis, "lstm_predict") as predict,
            patch.object(Jervis, "insert_predictions") as insert,
        ):
            Jervis.main()

        predict.assert_not_called()
        insert.assert_not_called()

    def test_main_combines_predictions_before_persisting(self):
        forecast = pd.DataFrame(
            {
                "Date": [pd.Timestamp("2026-08-12")],
                "Currency": ["USD"],
                "Predicted_Rates": [7.2],
                "Locals": ["2026-08-11 10:00:00 CST"],
            }
        )
        with (
            patch.object(Jervis, "CURRENCIES", ["美元"]),
            patch.object(Jervis, "get_currency_code", return_value="USD"),
            patch.object(Jervis, "fetch_history", return_value=pd.DataFrame(index=range(500))),
            patch.object(Jervis, "lstm_predict", return_value=forecast),
            patch.object(Jervis, "insert_predictions") as insert,
        ):
            Jervis.main()

        inserted = insert.call_args.args[0]
        pd.testing.assert_frame_equal(inserted, forecast)


if __name__ == "__main__":
    unittest.main()
