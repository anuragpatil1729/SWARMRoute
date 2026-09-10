from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Dict, Optional, Union
from src.models.road import TrafficLevel


class FuelModel(ABC):
    """
    Abstract base interface for fuel and CO2 emissions calculation.
    Enables seamless swapping between deterministic physics models and ML-trained models.
    """

    @abstractmethod
    def calculate_fuel(
        self,
        vehicle_type: str,
        vehicle_load: float,
        max_weight: float,
        distance: float,
        average_speed: float = 40.0,
        traffic_level: Union[TrafficLevel, str] = TrafficLevel.NORMAL,
        road_gradient: float = 0.0,
        stop_count: int = 0,
    ) -> float:
        """
        Calculates fuel consumed in Liters.
        """
        pass

    @abstractmethod
    def calculate_co2(self, fuel_liters: float, fuel_type: str = "diesel") -> float:
        """
        Calculates CO2 emissions in kilograms from fuel consumed.
        """
        pass


class DeterministicFuelModel(FuelModel):
    """
    Physics-grounded deterministic fuel consumption model for commercial fleet vehicles.
    Accounts for base fuel rate, payload weight factor, traffic-induced idling/braking,
    road incline/gradient, aerodynamic/speed variations, and acceleration from stops.
    """

    # Base fuel consumption at zero payload and nominal speed (Liters / 100 km)
    BASE_CONSUMPTION_L_PER_100KM: Dict[str, float] = {
        "heavy_duty": 30.0,
        "medium_duty": 20.0,
        "light": 10.0,
        "ev": 0.0,  # Zero direct diesel fuel (modeled separately for kWh)
    }

    # Fuel-to-CO2 emission factors (kg CO2 per Liter)
    EMISSION_FACTORS_KG_PER_LITER: Dict[str, float] = {
        "diesel": 2.68,
        "gasoline": 2.31,
        "cng": 1.90,
        "ev": 0.0,  # Zero tailpipe emissions
    }

    def __init__(
        self,
        payload_penalty_factor: float = 0.40,  # Up to 40% more fuel at max load
        fuel_per_stop_liters: float = 0.08,    # Fuel consumed per stop-and-accelerate cycle
        co2_factor: float = 2.68,
    ) -> None:
        self.payload_penalty_factor = payload_penalty_factor
        self.fuel_per_stop_liters = fuel_per_stop_liters
        self.co2_factor = co2_factor

    def calculate_fuel(
        self,
        vehicle_type: str,
        vehicle_load: float,
        max_weight: float,
        distance: float,
        average_speed: float = 40.0,
        traffic_level: Union[TrafficLevel, str] = TrafficLevel.NORMAL,
        road_gradient: float = 0.0,
        stop_count: int = 0,
    ) -> float:
        if distance <= 0.0:
            return 0.0

        v_type = vehicle_type.lower()
        base_rate = self.BASE_CONSUMPTION_L_PER_100KM.get(v_type, 28.0)

        # 1. Payload impact: linear scaling with load ratio
        load_ratio = min(1.0, max(0.0, vehicle_load / max(1.0, max_weight)))
        load_factor = 1.0 + (self.payload_penalty_factor * load_ratio)

        # 2. Traffic factor (stop-and-go, idling, brake-accelerate cycles)
        if isinstance(traffic_level, str):
            try:
                t_enum = TrafficLevel(traffic_level.upper())
            except ValueError:
                t_enum = TrafficLevel.NORMAL
        else:
            t_enum = traffic_level

        traffic_multipliers = {
            TrafficLevel.LIGHT: 0.95,
            TrafficLevel.NORMAL: 1.00,
            TrafficLevel.MODERATE: 1.25,
            TrafficLevel.HEAVY: 1.65,
            TrafficLevel.SEVERE: 2.20,
            TrafficLevel.BLOCKED: 3.00,
        }
        traffic_factor = traffic_multipliers.get(t_enum, 1.0)

        # 3. Road gradient impact (uphill work vs downhill coasting)
        # +1% gradient increases consumption by ~4%; downhill has diminishing return
        if road_gradient >= 0:
            gradient_factor = 1.0 + (0.04 * min(15.0, road_gradient))
        else:
            gradient_factor = max(0.70, 1.0 + (0.02 * max(-15.0, road_gradient)))

        # 4. Speed efficiency factor: optimal cruising is ~50-60 km/h
        # High speeds increase aerodynamic drag (quadratic)
        optimal_speed = 55.0
        if average_speed <= 0.0:
            speed_factor = 1.5
        elif average_speed <= optimal_speed:
            speed_factor = 1.0 + 0.2 * ((optimal_speed - average_speed) / optimal_speed)
        else:
            speed_factor = 1.0 + 0.4 * (((average_speed - optimal_speed) / optimal_speed) ** 1.5)

        effective_rate = base_rate * load_factor * traffic_factor * gradient_factor * speed_factor

        # Fuel for distance traversed + fuel wasted during stops
        travel_fuel = (effective_rate * distance) / 100.0
        stop_fuel = max(0, stop_count) * self.fuel_per_stop_liters

        return float(travel_fuel + stop_fuel)

    def calculate_co2(self, fuel_liters: float, fuel_type: str = "diesel") -> float:
        factor = self.EMISSION_FACTORS_KG_PER_LITER.get(fuel_type.lower(), self.co2_factor)
        return float(max(0.0, fuel_liters * factor))


class MLFuelModel(FuelModel):
    """
    Placeholder/Interface for ML-based fuel prediction model (Phase 11 extension).
    """

    def __init__(self, fallback_model: Optional[FuelModel] = None) -> None:
        self.fallback_model = fallback_model or DeterministicFuelModel()
        self.is_trained = False
        self.model = None

    def calculate_fuel(
        self,
        vehicle_type: str,
        vehicle_load: float,
        max_weight: float,
        distance: float,
        average_speed: float = 40.0,
        traffic_level: Union[TrafficLevel, str] = TrafficLevel.NORMAL,
        road_gradient: float = 0.0,
        stop_count: int = 0,
    ) -> float:
        if not self.is_trained or self.model is None:
            return self.fallback_model.calculate_fuel(
                vehicle_type=vehicle_type,
                vehicle_load=vehicle_load,
                max_weight=max_weight,
                distance=distance,
                average_speed=average_speed,
                traffic_level=traffic_level,
                road_gradient=road_gradient,
                stop_count=stop_count,
            )
        # ML model inference will be called here
        raise NotImplementedError("ML Fuel model training will be completed in Phase 11")

    def calculate_co2(self, fuel_liters: float, fuel_type: str = "diesel") -> float:
        return self.fallback_model.calculate_co2(fuel_liters, fuel_type)
