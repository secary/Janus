import os
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import torch
from sklearn.metrics import mean_squared_error
from torch import nn

from .base import BasePredictor


class RateLSTM(nn.Module, BasePredictor):
    def __init__(self, input_dim=1, hidden_dim=64, num_layers=2, dropout=0.2):
        super().__init__()
        self.lstm = nn.LSTM(
            input_dim, hidden_dim, num_layers, batch_first=True, dropout=dropout
        )
        self.fc = nn.Linear(hidden_dim, 1)

    def forward(self, x):
        out, _ = self.lstm(x)
        return self.fc(out[:, -1, :])

    def train_model(self, X, y, epochs, batch_size, lr, device):
        self.to(device)
        criterion = nn.MSELoss()
        optimizer = torch.optim.Adam(self.parameters(), lr=lr)
        self.train()
        for _ in range(epochs):
            for i in range(0, len(X), batch_size):
                xb, yb = (
                    X[i : i + batch_size].to(device),
                    y[i : i + batch_size].to(device),
                )
                optimizer.zero_grad()
                loss = criterion(self(xb), yb)
                loss.backward()
                optimizer.step()

    def predict(self, X):
        self.eval()
        with torch.no_grad():
            return self(X.to(next(self.parameters()).device))

    def save(self, path):
        torch.save(self.state_dict(), path)

    def load(self, path):
        self.load_state_dict(torch.load(path))
        self.eval()

    @classmethod
    def tune(
        cls,
        X: torch.Tensor,
        y: torch.Tensor,
        currency: str,
        device: str,
        save_dir: str,
        epoch_candidates: list[int] | None = None,
        batch_candidates: list[int] | None = None,
        lr_candidates: list[float] | None = None,
        model_factory: Callable[[], "RateLSTM"] | None = None,
    ) -> dict[str, Any]:
        os.makedirs(save_dir, exist_ok=True)
        epoch_candidates = epoch_candidates or [50, 100]
        batch_candidates = batch_candidates or [32, 64]
        lr_candidates = lr_candidates or [1e-2, 1e-3, 1e-4]
        model_factory = model_factory or cls

        n_val = int(len(X) * 0.2)
        X_train, X_val = X[:-n_val], X[-n_val:]
        y_train, y_val = y[:-n_val], y[-n_val:]
        best_mse = float("inf")
        best_config = {}

        for epochs in epoch_candidates:
            for batch_size in batch_candidates:
                for lr in lr_candidates:
                    model = model_factory().to(device)
                    model.train_model(X_train, y_train, epochs, batch_size, lr, device)
                    predictions = (
                        model.predict(X_val.to(device)).cpu().numpy().flatten()
                    )
                    mse = mean_squared_error(y_val.cpu().numpy().flatten(), predictions)
                    if mse < best_mse:
                        best_mse = mse
                        model_path = os.path.join(
                            save_dir,
                            f"{cls.__name__}_{currency}_{datetime.now(UTC):%Y%m}.pth",
                        )
                        model.save(model_path)
                        best_config = {
                            "epochs": epochs,
                            "batch_size": batch_size,
                            "lr": lr,
                            "val_mse": mse,
                            "model_path": model_path,
                        }

        return best_config
