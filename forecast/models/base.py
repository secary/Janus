from abc import ABC, abstractmethod
import torch

class BasePredictor(ABC):
    @abstractmethod
    def train(self, X: torch.Tensor, y: torch.Tensor):
        pass

    @abstractmethod
    def predict(self, X: torch.Tensor) -> torch.Tensor:
        pass

    @abstractmethod
    def save(self, path: str):
        pass

    @abstractmethod
    def load(self, path: str):
        pass
