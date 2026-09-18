from __future__ import annotations
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, root_mean_squared_error, r2_score
from sklearn.model_selection import train_test_split

from src.prediction.base import BasePredictor


class TravelTimePredictor(BasePredictor):
    """
    Predicts edge and route travel times considering:
      - distance (km)
      - time of day (hours, 0-24)
      - day of week (0-6)
      - historical speed (km/h)
      - traffic congestion level (0 to 5)
      - road type (highway, arterial, urban)
      - vehicle type (heavy, medium, light)
      - vehicle load (kg)
    """

    FEATURE_NAMES = [
        "distance",
        "time_of_day",
        "day_of_week",
        "historical_speed",
        "traffic_level",
        "road_type",
        "vehicle_type",
        "vehicle_load",
    ]

    def __init__(self, random_state: int = 42) -> None:
        super().__init__(model_name="TravelTimePredictor")
        self.random_state = random_state
        # HistGradientBoosting is fast, robust, and natively handles non-linear interactions
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
            raise ValueError("TravelTimePredictor model is not trained yet.")
        preds = self.model.predict(X)
        return np.maximum(preds, 0.01)  # Travel time must be non-negative

    def predict_single(
        self,
        distance: float,
        time_of_day: float = 9.0,
        day_of_week: int = 2,
        historical_speed: float = 45.0,
        traffic_level: Any = 1,
        road_type: int = 1,
        vehicle_type: int = 0,
        vehicle_load: float = 100.0,
    ) -> float:
        if isinstance(traffic_level, str):
            mapping = {"LIGHT": 0, "NORMAL": 1, "MODERATE": 2, "HEAVY": 3, "SEVERE": 4, "BLOCKED": 5}
            traffic_level = mapping.get(traffic_level.upper(), 1)
        elif hasattr(traffic_level, "value") and isinstance(traffic_level.value, str):
            mapping = {"LIGHT": 0, "NORMAL": 1, "MODERATE": 2, "HEAVY": 3, "SEVERE": 4, "BLOCKED": 5}
            traffic_level = mapping.get(traffic_level.value.upper(), 1)
        elif hasattr(traffic_level, "value") and isinstance(traffic_level.value, (int, float)):
            traffic_level = int(traffic_level.value)
        features = np.array(
            [[distance, time_of_day, day_of_week, historical_speed, float(traffic_level), road_type, vehicle_type, vehicle_load]]
        )
        return float(self.predict(features)[0])

    def predict_trip(
        self,
        distance_km: float,
        traffic_level: int = 1,
        hour_of_day: float = 9.0,
        is_weekend: bool = False,
        historical_speed: float = 45.0,
        road_type: int = 1,
        vehicle_type: int = 0,
        vehicle_load: float = 100.0,
    ) -> float:
        """Alias for trip-level travel time prediction in hours."""
        day_of_week = 5 if is_weekend else 2
        return self.predict_single(
            distance=distance_km,
            time_of_day=hour_of_day,
            day_of_week=day_of_week,
            historical_speed=historical_speed,
            traffic_level=traffic_level,
            road_type=road_type,
            vehicle_type=vehicle_type,
            vehicle_load=vehicle_load,
        )

    def evaluate(self, X_test: np.ndarray, y_test: np.ndarray) -> Dict[str, float]:
        preds = self.predict(X_test)
        mae = float(mean_absolute_error(y_test, preds))
        rmse = float(root_mean_squared_error(y_test, preds))
        r2 = float(r2_score(y_test, preds))
        return {
            "mae": round(mae, 4),
            "rmse": round(rmse, 4),
            "r2_score": round(r2, 4),
            "sample_count": len(y_test),
        }

    @staticmethod
    def generate_synthetic_trip_data(
        num_samples: int = 5000, seed: int = 42
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Generates realistic synthetic fleet trip observations:
          - Incorporates diurnal morning/evening rush-hour congestion peaks
          - Weekend vs weekday speed profiles
          - Payload and vehicle type speed degradation
        """
        rng = np.random.default_rng(seed)

        distances = rng.uniform(1.0, 60.0, size=num_samples)
        times_of_day = rng.uniform(6.0, 22.0, size=num_samples)
        days_of_week = rng.integers(0, 7, size=num_samples)
        road_types = rng.integers(0, 3, size=num_samples)  # 0: Highway, 1: Arterial, 2: Urban
        vehicle_types = rng.integers(0, 3, size=num_samples)  # 0: Heavy, 1: Medium, 2: Light
        loads = rng.uniform(0.0, 200.0, size=num_samples)

        # Base nominal speed by road type
        base_speeds = np.where(road_types == 0, 75.0, np.where(road_types == 1, 45.0, 30.0))

        # Congestion probability based on hour of day (rush hours: 8-10 AM, 17-19 PM)
        is_weekday = days_of_week < 5
        morning_peak = np.exp(-0.5 * ((times_of_day - 8.5) / 1.2) ** 2)
        evening_peak = np.exp(-0.5 * ((times_of_day - 17.5) / 1.5) ** 2)
        congestion_intensity = np.where(is_weekday, 0.7 * morning_peak + 0.8 * evening_peak, 0.2)

        # Discretize traffic level (0 to 5)
        traffic_raw = rng.uniform(0.0, 1.0, size=num_samples) + congestion_intensity
        traffic_levels = np.clip((traffic_raw * 2.5).astype(int), 0, 5)

        # Speed multipliers
        traffic_multipliers = np.array([1.1, 1.0, 0.75, 0.50, 0.25, 0.05])
        effective_speed = base_speeds * traffic_multipliers[traffic_levels]

        # Vehicle type & load penalty (heavy trucks 10% slower when fully loaded)
        load_penalty = 1.0 - (0.10 * (vehicle_types == 0) * (loads / 200.0))
        effective_speed = np.maximum(5.0, effective_speed * load_penalty)

        # Historical speed feature with minor noise
        historical_speeds = np.maximum(5.0, effective_speed + rng.normal(0, 3.0, size=num_samples))

        # True travel time = distance / effective_speed + stochastic signal delays
        stochastic_delay = rng.exponential(scale=0.03, size=num_samples)  # ~1.8 mins avg delay
        travel_times = (distances / effective_speed) + stochastic_delay

        X = np.column_stack([
            distances,
            times_of_day,
            days_of_week,
            historical_speeds,
            traffic_levels,
            road_types,
            vehicle_types,
            loads,
        ])
        y = travel_times

        return X, y
