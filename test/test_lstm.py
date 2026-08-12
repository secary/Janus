import unittest
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock

import torch

from app.models.lstm import RateLSTM


class RateLSTMTests(unittest.TestCase):
    def test_forward_returns_one_prediction_per_sequence(self):
        model = RateLSTM(input_dim=1, hidden_dim=8, num_layers=1, dropout=0.0)
        inputs = torch.rand(4, 48, 1)

        output = model(inputs)

        self.assertEqual(tuple(output.shape), (4, 1))

    def test_predict_disables_gradient_tracking(self):
        model = RateLSTM(input_dim=1, hidden_dim=8, num_layers=1, dropout=0.0)

        output = model.predict(torch.rand(2, 48, 1))

        self.assertFalse(output.requires_grad)
        self.assertFalse(model.training)

    def test_saved_model_can_be_loaded_with_same_parameters(self):
        source = RateLSTM(input_dim=1, hidden_dim=8, num_layers=1, dropout=0.0)
        target = RateLSTM(input_dim=1, hidden_dim=8, num_layers=1, dropout=0.0)

        with TemporaryDirectory() as directory:
            path = f"{directory}/model.pth"
            source.save(path)
            target.load(path)

        for source_parameter, target_parameter in zip(
            source.parameters(), target.parameters(), strict=True
        ):
            torch.testing.assert_close(source_parameter, target_parameter)

    def test_tune_selects_configuration_with_lowest_validation_mse(self):
        features = torch.arange(40, dtype=torch.float32).reshape(20, 2, 1)
        targets = torch.arange(20, dtype=torch.float32).reshape(20, 1)
        first_model = MagicMock()
        second_model = MagicMock()
        first_model.to.return_value = first_model
        second_model.to.return_value = second_model
        first_model.predict.return_value = torch.full((4, 1), 17.0)
        second_model.predict.return_value = targets[-4:].clone()

        models = iter([first_model, second_model])
        with TemporaryDirectory() as directory:
            result = RateLSTM.tune(
                X=features,
                y=targets,
                currency="USD",
                device="cpu",
                epoch_candidates=[1],
                batch_candidates=[4],
                lr_candidates=[0.1, 0.01],
                save_dir=directory,
                model_factory=lambda: next(models),
            )

        self.assertEqual(result["lr"], 0.01)
        self.assertEqual(result["val_mse"], 0.0)
        first_model.save.assert_called_once()
        second_model.save.assert_called_once()


if __name__ == "__main__":
    unittest.main()
