import unittest
from unittest.mock import patch

from app import train


class TrainingCompatibilityTests(unittest.TestCase):
    def test_train_currency_delegates_to_tuner(self):
        with patch.object(train, "tune_currency", return_value={"score": 1.0}) as tune:
            result = train.train_currency("lstm", "USD")
        tune.assert_called_once_with("lstm", "USD")
        self.assertEqual(result, {"score": 1.0})

    def test_main_delegates_to_tuning_orchestration(self):
        with patch.object(train, "tune_main") as tune_main:
            train.main("lstm")
        tune_main.assert_called_once_with("lstm")


if __name__ == "__main__":
    unittest.main()
