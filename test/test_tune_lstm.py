import unittest
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

import torch
from main import tune_lstm


class GridSearchTests(unittest.TestCase):
    def test_selects_and_saves_configuration_with_lowest_validation_mse(self):
        features = torch.arange(40, dtype=torch.float32).reshape(20, 2, 1)
        targets = torch.arange(20, dtype=torch.float32).reshape(20, 1)
        first_model = MagicMock()
        second_model = MagicMock()
        first_model.to.return_value = first_model
        second_model.to.return_value = second_model
        first_model.predict.return_value = torch.tensor(
            [[17.0], [17.0], [17.0], [17.0]]
        )
        second_model.predict.return_value = targets[-4:].clone()

        with (
            TemporaryDirectory() as directory,
            patch.object(
                tune_lstm, "RateLSTM", side_effect=[first_model, second_model]
            ),
        ):
            result = tune_lstm.grid_search_lstm(
                X=features,
                y=targets,
                currency="USD",
                device="cpu",
                epoch_candidates=[1],
                batch_candidates=[4],
                lr_candidates=[0.1, 0.01],
                save_dir=directory,
            )

        self.assertEqual(result["lr"], 0.01)
        self.assertEqual(result["val_mse"], 0.0)
        first_model.save.assert_called_once()
        second_model.save.assert_called_once()


if __name__ == "__main__":
    unittest.main()
