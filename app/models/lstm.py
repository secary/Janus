import torch
import torch.nn as nn
from .base import BasePredictor

class RateLSTM(nn.Module, BasePredictor):
    def __init__(self, input_dim=1, hidden_dim=64, num_layers=2, dropout=0.2):
        super().__init__()
        self.lstm = nn.LSTM(input_dim, hidden_dim, num_layers, batch_first=True, dropout=dropout)
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
                xb, yb = X[i:i+batch_size].to(device), y[i:i+batch_size].to(device)
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
