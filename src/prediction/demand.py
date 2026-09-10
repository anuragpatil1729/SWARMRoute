from __future__ import annotations
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, root_mean_squared_error, r2_score
from sklearn.model_selection import train_test_split

from src.prediction.base import BasePredictor


class DemandPredictor(BasePredictor):
    """
    Predicts customer/zone future order demand volumes based on:
      - zone_id (numeric encoding)
      - day_of_week (0 to 6)
      - hour_slot (0 to 23)
      - historical_mean_demand
      - rolling_7d_avg
      - seasonal_cycle (sine/cosine of day of year)
    """

    FEATURE_NAMES = [
        "zone_id",
        "day_of_week",
        "hour_slot",
        "historical_mean",
        "rolling_avg",
        "seasonal_sin",
        "seasonal_cos",
    ]

    def __init__(self, random_state: int = 42) -> None:
        super().__init__(model_name="DemandPredictor")
        self.random_state = random_state
        self.model = HistGradientBoostingRegressor(
            loss="squared_error",
            max_iter=300,
            learning_rate=0.05,
            min_samples_leaf=20,
            l2_regularization=0.1,
            early_stopping=True,
            n_iter_no_change=15,
            random_state=self.random_state,
        )

    def train(self, X: np.ndarray, y: np.ndarray, test_size: float = 0.2) -> Dict[str, float]:
        X_train, X_val, y_train, y_val = train_test_split(
            X, y, test_size=test_size, random_state=self.random_state
        )
        self.model.fit(X_train, y_train)
        self.is_trained = True

        self.metrics = self.evaluate(X_val, y_val)
        return self.metrics

    def predict(self, X: np.ndarray) -> np.ndarray:
        if not self.is_trained or self.model is None:
            raise ValueError("DemandPredictor model is not trained yet.")
        preds = self.model.predict(X)
        return np.maximum(preds, 0.0)

    def evaluate(self, X_test: np.ndarray, y_test: np.ndarray) -> Dict[str, float]:
        preds = self.predict(X_test)
        mae = float(mean_absolute_error(y_test, preds))
        rmse = float(root_mean_squared_error(y_test, preds))
        r2 = float(r2_score(y_test, preds))

        # Compare against simple historical mean baseline (feature index 3)
        hist_mean_preds = X_test[:, 3]
        base_mae = float(mean_absolute_error(y_test, hist_mean_preds))
        base_rmse = float(root_mean_squared_error(y_test, hist_mean_preds))

        return {
            "ml_mae": round(mae, 4),
            "ml_rmse": round(rmse, 4),
            "ml_r2_score": round(r2, 4),
            "baseline_mean_mae": round(base_mae, 4),
            "baseline_mean_rmse": round(base_rmse, 4),
            "sample_count": len(y_test),
        }

    @staticmethod
    def generate_synthetic_demand_data(
        num_samples: int = 5000, num_zones: int = 20, seed: int = 42
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Simulates customer demand distributions consistent with the Mendeley Dynamic VRP dataset:
        Weekly periodicity, zone baseline variances, and business vs residential patterns.
        """
        rng = np.random.default_rng(seed)

        zone_ids = rng.integers(0, num_zones, size=num_samples)
        days_of_week = rng.integers(0, 7, size=num_samples)
        hour_slots = rng.integers(8, 20, size=num_samples)
        day_of_year = rng.integers(1, 365, size=num_samples)

        # Base demand per zone
        zone_bases = rng.uniform(10.0, 50.0, size=num_zones)
        hist_means = zone_bases[zone_ids]

        # Cyclical features
        seasonal_sin = np.sin(2 * np.pi * day_of_year / 365.0)
        seasonal_cos = np.cos(2 * np.pi * day_of_year / 365.0)

        # Day of week multiplier (weekdays higher demand for commercial logistics)
        dow_factor = np.where(days_of_week < 5, 1.2, 0.7)
        hour_factor = 1.0 + 0.3 * np.sin((hour_slots - 8) / 12.0 * np.pi)

        true_demand = (
            hist_means * dow_factor * hour_factor
            + 5.0 * seasonal_sin
            + rng.normal(0, 3.0, size=num_samples)
        )
        true_demand = np.maximum(1.0, true_demand)

        # Rolling 7d average is a smoothed noisy observation of the true trend
        rolling_avg = hist_means * dow_factor + rng.normal(0, 2.0, size=num_samples)

        X = np.column_stack([
            zone_ids,
            days_of_week,
            hour_slots,
            hist_means,
            rolling_avg,
            seasonal_sin,
            seasonal_cos,
        ])
        y = true_demand

        return X, y
