from __future__ import annotations
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Union
import joblib
import numpy as np


class BasePredictor(ABC):
    """
    Modular interface for all Layer A machine learning prediction models.
    Supports train, predict, evaluate, save, and load.
    """

    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        self.model: Optional[Any] = None
        self.is_trained: bool = False
        self.metrics: Dict[str, float] = {}

    @abstractmethod
    def train(self, X: np.ndarray, y: np.ndarray, **kwargs: Any) -> Dict[str, float]:
        """Trains the internal model and returns training/validation metrics."""
        pass

    @abstractmethod
    def predict(self, X: np.ndarray) -> np.ndarray:
        """Makes predictions on input feature matrix X."""
        pass

    @abstractmethod
    def evaluate(self, X_test: np.ndarray, y_test: np.ndarray) -> Dict[str, float]:
        """Evaluates model performance and returns metric dictionary (MAE, RMSE, R2)."""
        pass

    def save(self, filepath: Union[str, Path]) -> Path:
        """Saves model weights, configuration, and metadata."""
        if not self.is_trained or self.model is None:
            raise ValueError(f"Cannot save untrained model '{self.model_name}'")
        p = Path(filepath)
        p.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "model_name": self.model_name,
            "model": self.model,
            "is_trained": self.is_trained,
            "metrics": self.metrics,
        }
        joblib.dump(payload, p)
        return p

    def load(self, filepath: Union[str, Path]) -> None:
        """Loads model weights, configuration, and metadata from disk."""
        p = Path(filepath)
        if not p.exists():
            raise FileNotFoundError(f"Model checkpoint not found at: {p}")
        payload = joblib.load(p)
        self.model_name = payload.get("model_name", self.model_name)
        self.model = payload["model"]
        self.is_trained = payload.get("is_trained", True)
        self.metrics = payload.get("metrics", {})
