from __future__ import annotations
import math
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union
from pydantic import BaseModel, Field

from src.models.order import Order, OrderStatus
from src.models.vehicle import Vehicle


# Default multi-objective cost weights matching configs/config.yaml
DEFAULT_OBJECTIVE_WEIGHTS: Dict[str, float] = {
    "distance": 1.0,
    "fuel": 2.0,
    "delay": 10.0,
    "emissions": 3.0,
    "vehicle_usage": 5.0,
    "risk": 4.0,
}

DEFAULT_CO2_PER_LITER: float = 2.68


def calculate_total_distance(
    routes: Sequence[Sequence[int]],
    distance_matrix: Union[Dict[Tuple[int, int], float], Any],
) -> float:
    """
    Calculates total route distance across all vehicles.
    Supports either a dictionary (u, v) -> dist or a 2D matrix/list.
    """
    total = 0.0
    for route in routes:
        if len(route) < 2:
            continue
        for i in range(len(route) - 1):
            u, v = route[i], route[i + 1]
            if isinstance(distance_matrix, dict):
                dist = distance_matrix.get((u, v), distance_matrix.get((v, u), 0.0))
            else:
                dist = distance_matrix[u][v]
            total += float(dist)
    return round(total, 2)


def calculate_total_travel_time(
    routes: Sequence[Sequence[int]],
    road_network: Any,
    default_speed_kmh: float = 40.0,
) -> float:
    """
    Calculates total travel time across all vehicle routes in hours,
    taking into account road-specific congestion multipliers if available.
    """
    total_time_hrs = 0.0
    for route in routes:
        if len(route) < 2:
            continue
        for i in range(len(route) - 1):
            u, v = route[i], route[i + 1]
            if hasattr(road_network, "get_travel_time"):
                total_time_hrs += road_network.get_travel_time(u, v, default_speed_kmh)
            elif hasattr(road_network, "get_distance"):
                dist = road_network.get_distance(u, v)
                total_time_hrs += dist / max(default_speed_kmh, 1.0)
            else:
                total_time_hrs += 0.0
    return round(total_time_hrs, 2)


def calculate_total_fuel(
    routes: Sequence[Sequence[int]],
    orders_map: Dict[str, Order],
    node_to_order_map: Dict[int, str],
    vehicle: Vehicle,
    road_network: Any,
    fuel_model: Optional[Any] = None,
) -> float:
    """
    Physically consistent route fuel consumption with leg-by-leg payload tracking.
    """
    from src.prediction.fuel import calculate_route_fuel, DeterministicFuelModel

    model = fuel_model or DeterministicFuelModel()
    total_fuel = 0.0

    for route in routes:
        if len(route) < 2:
            continue
        # Delivery orders in this specific route
        route_orders = [
            orders_map[node_to_order_map[node]]
            for node in route
            if node in node_to_order_map and node_to_order_map[node] in orders_map
        ]
        route_fuel = calculate_route_fuel(
            route=list(route),
            orders=route_orders,
            vehicle=vehicle,
            road_network=road_network,
            fuel_model=model,
        )
        total_fuel += route_fuel

    return round(total_fuel, 2)


def calculate_total_emissions(
    fuel_liters: float,
    emission_factor_kg_per_l: float = DEFAULT_CO2_PER_LITER,
) -> float:
    """
    Calculates total CO2 emissions in kg from diesel fuel consumed.
    """
    return round(fuel_liters * emission_factor_kg_per_l, 2)


def calculate_total_cost(
    distance_km: float,
    fuel_liters: float,
    delay_hours: float,
    emissions_kg: float,
    vehicles_used: int,
    risk: float = 0.0,
    weights: Optional[Dict[str, float]] = None,
) -> float:
    """
    Standardized multi-objective fleet cost function.
    All algorithms must evaluate fleet cost using this identical formula.
    """
    w = weights or DEFAULT_OBJECTIVE_WEIGHTS
    cost = (
        w.get("distance", 1.0) * distance_km
        + w.get("fuel", 2.0) * fuel_liters
        + w.get("delay", 10.0) * delay_hours
        + w.get("emissions", 3.0) * emissions_kg
        + w.get("vehicle_usage", 5.0) * vehicles_used
        + w.get("risk", 4.0) * risk
    )
    return round(cost, 2)


def calculate_late_deliveries(orders: Sequence[Order]) -> Tuple[int, float]:
    """
    Determines late order count and maximum lateness (in minutes or hours)
    across all orders.
    """
    late_count = 0
    max_lateness = 0.0
    for o in orders:
        is_l = o.is_late() if callable(getattr(o, "is_late", None)) else getattr(o, "is_late", False)
        if is_l:
            late_count += 1
            lat = o.lateness() if callable(getattr(o, "lateness", None)) else getattr(o, "lateness", 0.0)
            max_lateness = max(max_lateness, float(lat))
    return late_count, round(max_lateness, 2)


def calculate_completion_rate(total_orders: int, delivered_orders: int) -> float:
    """
    Calculates percentage of successfully completed orders.
    """
    if total_orders <= 0:
        return 0.0
    return round((delivered_orders / total_orders) * 100.0, 1)


def calculate_vehicle_utilization(vehicles: Sequence[Vehicle]) -> float:
    """
    Calculates average capacity utilization percentage across deployed vehicles.
    """
    active = [v for v in vehicles if len(v.current_route) > 1 or v.current_cargo_weight > 0.0]
    if not active:
        return 0.0
    utilizations = [v.utilization_rate for v in active]
    return round((sum(utilizations) / len(utilizations)) * 100.0, 1)


class FleetMetrics(BaseModel):
    """
    Standardized benchmark metrics container.
    """
    system_name: str = Field(..., description="Name of the system or algorithm evaluated")
    dataset_name: str = Field(default="Solomon C101", description="Dataset or scenario name")
    num_vehicles_used: int = Field(default=0, description="Active trucks deployed")
    total_vehicles_available: int = Field(default=0, description="Total fleet size")
    total_orders: int = Field(default=0, description="Total order count evaluated")
    delivered_orders: int = Field(default=0, description="Successfully scheduled orders")
    completion_rate_pct: float = Field(default=0.0, description="Percentage of delivered orders")
    total_distance_km: float = Field(default=0.0, description="Total route distance (km)")
    total_travel_time_hrs: float = Field(default=0.0, description="Total travel time")
    total_fuel_liters: float = Field(default=0.0, description="Total diesel consumed (L)")
    total_co2_kg: float = Field(default=0.0, description="Total CO2 emissions (kg)")
    late_deliveries: int = Field(default=0, description="Number of orders served late")
    max_lateness: float = Field(default=0.0, description="Max lateness across orders")
    vehicle_utilization_pct: float = Field(default=0.0, description="Average payload capacity utilization")
    total_cost: float = Field(default=0.0, description="Aggregated multi-objective cost")
    runtime_seconds: float = Field(default=0.0, description="Algorithm computation runtime")

    def format_summary(self, currency_symbol: str = "₹") -> str:
        """Returns clean formatted text block matching project specifications."""
        return (
            f"Distance: {self.total_distance_km:,.2f} km\n"
            f"Fuel: {self.total_fuel_liters:,.2f} L\n"
            f"CO2: {self.total_co2_kg:,.2f} kg\n"
            f"Vehicles Used: {self.num_vehicles_used} / {self.total_vehicles_available}\n"
            f"Fleet Utilization: {self.vehicle_utilization_pct:.1f} %\n"
            f"Delivered: {self.delivered_orders} / {self.total_orders} ({self.completion_rate_pct:.1f} %)\n"
            f"Late deliveries: {self.late_deliveries}\n"
            f"Max lateness: {self.max_lateness:.1f}\n"
            f"Cost: {currency_symbol}{self.total_cost:,.2f}\n"
            f"Runtime: {self.runtime_seconds:.3f} sec"
        )
