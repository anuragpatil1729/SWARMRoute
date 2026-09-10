from __future__ import annotations
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, root_mean_squared_error, r2_score
from sklearn.model_selection import train_test_split

from src.prediction.base import BasePredictor
from src.prediction.fuel import DeterministicFuelModel
from src.models.road import TrafficLevel


class FuelConsumptionPredictor(BasePredictor):
    """
    ML Fuel Consumption Model trained on simulation trip records.
    Features:
      - distance (km)
      - vehicle_type_code (0: heavy_duty, 1: medium_duty, 2: light)
      - vehicle_load (kg)
      - average_speed (km/h)
      - traffic_level_code (0 to 5)
      - road_gradient (%)
      - stop_count (int)
    Target:
      - fuel_consumed (Liters)
    """

    FEATURE_NAMES = [
        "distance",
        "vehicle_type_code",
        "vehicle_load",
        "average_speed",
        "traffic_level_code",
        "road_gradient",
        "stop_count",
    ]

    VEHICLE_TYPE_MAP = {
        0: "heavy_duty",
        1: "medium_duty",
        2: "light",
    }

    def __init__(self, random_state: int = 42) -> None:
        super().__init__(model_name="FuelConsumptionPredictor")
        self.random_state = random_state
        self.model = HistGradientBoostingRegressor(
            loss="squared_error",
            max_iter=180,
            learning_rate=0.08,
            random_state=self.random_state,
        )
        self.physics_model = DeterministicFuelModel()

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
            raise ValueError("FuelConsumptionPredictor model is not trained yet.")
        preds = self.model.predict(X)
        return np.maximum(preds, 0.0)

    def evaluate(self, X_test: np.ndarray, y_test: np.ndarray) -> Dict[str, float]:
        preds = self.predict(X_test)
        mae = float(mean_absolute_error(y_test, preds))
        rmse = float(root_mean_squared_error(y_test, preds))
        r2 = float(r2_score(y_test, preds))

        # Comparative evaluation: Physics baseline on the same test set
        physics_preds = []
        traffic_levels = [
            TrafficLevel.LIGHT,
            TrafficLevel.NORMAL,
            TrafficLevel.MODERATE,
            TrafficLevel.HEAVY,
            TrafficLevel.SEVERE,
            TrafficLevel.BLOCKED,
        ]
        for row in X_test:
            dist, v_type_code, load, spd, traf_code, grad, stops = row
            v_type_str = self.VEHICLE_TYPE_MAP.get(int(v_type_code), "heavy_duty")
            t_enum = traffic_levels[min(5, max(0, int(traf_code)))]
            p_fuel = self.physics_model.calculate_fuel(
                vehicle_type=v_type_str,
                vehicle_load=load,
                max_weight=200.0,
                distance=dist,
                average_speed=spd,
                traffic_level=t_enum,
                road_gradient=grad,
                stop_count=int(stops),
            )
            physics_preds.append(p_fuel)

        physics_preds_arr = np.array(physics_preds)
        phys_mae = float(mean_absolute_error(y_test, physics_preds_arr))
        phys_rmse = float(root_mean_squared_error(y_test, physics_preds_arr))

        return {
            "ml_mae": round(mae, 4),
            "ml_rmse": round(rmse, 4),
            "ml_r2_score": round(r2, 4),
            "physics_mae": round(phys_mae, 4),
            "physics_rmse": round(phys_rmse, 4),
            "sample_count": len(y_test),
        }

    @staticmethod
    def generate_synthetic_fuel_data(
        num_samples: int = 5000, seed: int = 42
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Generates simulated fuel consumption trip data with real-world noise factors:
        driver behavior, wind resistance variations, and auxiliary refrigeration loads.
        """
        rng = np.random.default_rng(seed)
        physics = DeterministicFuelModel()

        distances = rng.uniform(2.0, 100.0, size=num_samples)
        vehicle_types = rng.integers(0, 3, size=num_samples)
        loads = rng.uniform(0.0, 200.0, size=num_samples)
        speeds = rng.uniform(20.0, 80.0, size=num_samples)
        traffic_codes = rng.integers(0, 6, size=num_samples)
        gradients = rng.uniform(-6.0, 8.0, size=num_samples)
        stops = rng.integers(1, 15, size=num_samples)

        traffic_levels = [
            TrafficLevel.LIGHT,
            TrafficLevel.NORMAL,
            TrafficLevel.MODERATE,
            TrafficLevel.HEAVY,
            TrafficLevel.SEVERE,
            TrafficLevel.BLOCKED,
        ]

        fuel_targets = []
        for i in range(num_samples):
            v_str = FuelConsumptionPredictor.VEHICLE_TYPE_MAP[vehicle_types[i]]
            t_enum = traffic_levels[traffic_codes[i]]
            base_f = physics.calculate_fuel(
                vehicle_type=v_str,
                vehicle_load=loads[i],
                max_weight=200.0,
                distance=distances[i],
                average_speed=speeds[i],
                traffic_level=t_enum,
                road_gradient=gradients[i],
                stop_count=int(stops[i]),
            )
            # Add stochastic environmental/driver variation (+/- 5%)
            driver_factor = rng.normal(1.0, 0.04)
            fuel_targets.append(max(0.1, base_f * driver_factor))

        X = np.column_stack([
            distances,
            vehicle_types,
            loads,
            speeds,
            traffic_codes,
            gradients,
            stops,
        ])
        y = np.array(fuel_targets)
        return X, y
