import unittest
from tempfile import TemporaryDirectory

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


if __name__ == "__main__":
    unittest.main()
