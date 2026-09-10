from __future__ import annotations
import time
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field

from src.models.order import Order, OrderStatus
from src.models.vehicle import Vehicle, VehicleStatus
from src.models.road import RoadNetwork, TrafficLevel
from src.models.fleet_state import FleetState
from src.prediction.fuel import FuelModel, DeterministicFuelModel
from src.optimization.vrptw import VRPTWSolver, OptimizationResult
from src.optimization.delivery_exchange import DeliveryExchangeEngine, DeliveryExchangePlan


class ReoptimizationResult(BaseModel):
    """
    Standard summary produced by self-healing re-optimization strategies.
    """
    strategy: str  # "LOCAL_RECOVERY" or "GLOBAL_RECOVERY"
    recovery_time_sec: float
    orders_recovered: int
    orders_failed: int
    active_vehicles: int
    total_distance_km: float
    total_fuel_liters: float
    total_co2_kg: float
    exchange_plan: Optional[DeliveryExchangePlan] = None
    routes: Dict[str, List[int]] = Field(default_factory=dict)


class DynamicReoptimizer:
    """
    Self-Healing Fleet Optimizer.
    Compares two strategic recovery paradigms when unexpected disruptions strike:
      1. Local Recovery: Reassigns only affected orders to nearby neighboring trucks.
      2. Global Recovery: Discards ongoing assignments and re-optimizes the entire fleet globally.
    """

    def __init__(
        self,
        fuel_model: Optional[FuelModel] = None,
        objective_weights: Optional[Dict[str, float]] = None,
    ) -> None:
        self.fuel_model = fuel_model or DeterministicFuelModel()
        self.objective_weights = objective_weights
        self.exchange_engine = DeliveryExchangeEngine(fuel_model=self.fuel_model)
        self.vrptw_solver = VRPTWSolver(
            fuel_model=self.fuel_model, objective_weights=self.objective_weights
        )

    def recover_local(
        self,
        fleet_state: FleetState,
        broken_vehicle_id: str,
        road_network: RoadNetwork,
        node_id_map: Dict[str, int],
        current_time_mins: float,
    ) -> ReoptimizationResult:
        """
        Executes fast local peer-to-peer load swapping without disrupting un-affected vehicles.
        """
        start_time = time.time()
        broken_truck = fleet_state.vehicles.get(broken_vehicle_id)
        if not broken_truck:
            raise ValueError(f"Vehicle {broken_vehicle_id} not found in fleet.")

        # Identify stranded orders from the broken truck's assigned orders
        stranded = [
            fleet_state.active_orders[oid]
            for oid in broken_truck.assigned_orders
            if oid in fleet_state.active_orders
        ]

        # Operational vehicles (exclude broken truck)
        operational_trucks = [
            v for v in fleet_state.vehicles.values()
            if v.vehicle_id != broken_vehicle_id and v.status != VehicleStatus.BROKEN_DOWN
        ]

        # Plan order swaps
        plan = self.exchange_engine.plan_swaps(
            broken_vehicle=broken_truck,
            stranded_orders=stranded,
            operational_vehicles=operational_trucks,
            road_network=road_network,
            node_id_map=node_id_map,
            current_time_mins=current_time_mins,
        )

        # Clear remaining routes on the broken truck
        broken_truck.current_route = [0]
        broken_truck.assigned_orders = []

        elapsed = time.time() - start_time

        # Calculate fleet totals across all operational trucks
        total_dist = 0.0
        total_fuel = 0.0
        total_co2 = 0.0
        routes_summary = {}

        for v in operational_trucks:
            if len(v.current_route) > 2:
                demands = {
                    node: road_network.graph.nodes[node].get("demand", 0.0)
                    for node in v.current_route
                    if node != 0
                }
                d, f, c = self.fuel_model.calculate_route_fuel(
                    route=v.current_route,
                    road_network=road_network,
                    vehicle_type=v.vehicle_type,
                    max_weight=v.max_weight,
                    average_speed=v.average_speed,
                    customer_demands=demands,
                )
                total_dist += d
                total_fuel += f
                total_co2 += c
                routes_summary[v.vehicle_id] = list(v.current_route)

        return ReoptimizationResult(
            strategy="LOCAL_RECOVERY",
            recovery_time_sec=round(elapsed, 4),
            orders_recovered=len(stranded) - len(plan.unabsorbed_orders),
            orders_failed=len(plan.unabsorbed_orders),
            active_vehicles=len(routes_summary),
            total_distance_km=round(total_dist, 2),
            total_fuel_liters=round(total_fuel, 2),
            total_co2_kg=round(total_co2, 2),
            exchange_plan=plan,
            routes=routes_summary,
        )

    def recover_global(
        self,
        fleet_state: FleetState,
        road_network: RoadNetwork,
        remaining_orders: List[Order],
        time_limit_sec: int = 10,
    ) -> ReoptimizationResult:
        """
        Runs global OR-Tools fleet re-optimization across all operational trucks.
        """
        start_time = time.time()
        operational_trucks = [
            v for v in fleet_state.vehicles.values()
            if v.status != VehicleStatus.BROKEN_DOWN
        ]

        opt_result = self.vrptw_solver.solve(
            vehicles=operational_trucks,
            orders=remaining_orders,
            road_network=road_network,
            time_limit_sec=time_limit_sec,
        )

        elapsed = time.time() - start_time
        return ReoptimizationResult(
            strategy="GLOBAL_RECOVERY",
            recovery_time_sec=round(elapsed, 3),
            orders_recovered=len(remaining_orders) - len(opt_result.unassigned_orders),
            orders_failed=len(opt_result.unassigned_orders),
            active_vehicles=opt_result.active_vehicles_count,
            total_distance_km=opt_result.total_distance,
            total_fuel_liters=opt_result.total_fuel,
            total_co2_kg=opt_result.total_emissions,
            routes=opt_result.routes,
        )
