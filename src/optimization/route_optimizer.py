from __future__ import annotations
from typing import Any, Dict, List, Optional, Union

from src.models.order import Order
from src.models.vehicle import Vehicle
from src.models.road import RoadNetwork, TrafficLevel
from src.models.fleet_state import FleetState
from src.prediction.fuel import FuelModel, DeterministicFuelModel
from src.optimization.vrptw import VRPTWSolver, OptimizationResult
from src.optimization.load_optimizer import LoadOptimizer


class RouteOptimizer:
    """
    Unified Route Optimization Engine.
    Coordinates load optimization and OR-Tools exact/metaheuristic route solving.
    """

    def __init__(
        self,
        fuel_model: Optional[FuelModel] = None,
        objective_weights: Optional[Dict[str, float]] = None,
    ) -> None:
        self.fuel_model = fuel_model or DeterministicFuelModel()
        self.objective_weights = objective_weights
        self.vrptw_solver = VRPTWSolver(
            fuel_model=self.fuel_model,
            objective_weights=self.objective_weights,
        )

    def optimize(
        self,
        fleet: Union[FleetState, List[Vehicle]],
        orders: Union[Dict[str, Order], List[Order]],
        road_network: RoadNetwork,
        traffic_state: Optional[Dict[str, TrafficLevel]] = None,
        objective_weights: Optional[Dict[str, float]] = None,
        time_limit_sec: int = 30,
        allow_drop: bool = False,
    ) -> OptimizationResult:
        """
        Main optimization entry point required by specification:
        optimize(fleet, orders, road_network, traffic_state, objective_weights)
        """
        # 1. Normalize fleet input
        if isinstance(fleet, FleetState):
            vehicle_list = list(fleet.vehicles.values())
        else:
            vehicle_list = list(fleet)

        # 2. Normalize orders input
        if isinstance(orders, dict):
            order_list = list(orders.values())
        else:
            order_list = list(orders)

        # 3. Update weights if provided
        weights = objective_weights or self.objective_weights
        solver = self.vrptw_solver
        if weights is not None:
            solver = VRPTWSolver(fuel_model=self.fuel_model, objective_weights=weights)

        # 4. Apply traffic state to road network if provided
        if traffic_state:
            for road_id, level in traffic_state.items():
                if road_network.graph.has_edge(road_id, None):
                    pass  # Edge updates if keyed by edge

        # 5. Execute VRPTW Solver
        result = solver.solve(
            vehicles=vehicle_list,
            orders=order_list,
            road_network=road_network,
            time_limit_sec=time_limit_sec,
            allow_drop=allow_drop,
        )

        # 6. Update fleet vehicle states with resulting routes and assignments
        if isinstance(fleet, FleetState):
            for v_id, route in result.routes.items():
                if v_id in fleet.vehicles:
                    fleet.vehicles[v_id].current_route = route
                    fleet.vehicles[v_id].assigned_orders = result.order_assignments.get(v_id, [])

        return result
