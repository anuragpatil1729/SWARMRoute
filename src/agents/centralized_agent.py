from __future__ import annotations
import time
from typing import Any, Dict, List, Optional, Tuple

from src.models.fleet_state import FleetState, ConnectivityState
from src.models.order import Order, OrderStatus
from src.models.vehicle import Vehicle, VehicleStatus
from src.models.road import RoadNetwork
from src.optimization.route_optimizer import RouteOptimizer, OptimizationResult
from src.optimization.dynamic_reoptimizer import DynamicReoptimizer


class CentralizedAgent:
    """
    Conventional Central Dispatcher Agent.
    Assumes continuous cloud connectivity and central state access.
    When disconnected (Internet failure), it is completely blind and unable
    to issue reroutes or recover stranded orders.
    """

    def __init__(
        self,
        route_optimizer: Optional[RouteOptimizer] = None,
        reoptimizer: Optional[DynamicReoptimizer] = None,
    ) -> None:
        self.route_optimizer = route_optimizer or RouteOptimizer()
        self.reoptimizer = reoptimizer or DynamicReoptimizer()
        self.last_replan_timestamp: float = 0.0
        self.total_reoptimizations: int = 0

    def can_communicate(self, fleet_state: FleetState) -> bool:
        """Centralized dispatcher requires CLOUD_MODE to communicate with fleet."""
        return fleet_state.connectivity_state == ConnectivityState.CLOUD_MODE

    def handle_breakdown(
        self,
        fleet_state: FleetState,
        road_network: RoadNetwork,
        broken_vehicle_id: str,
        current_time_mins: float,
    ) -> Optional[OptimizationResult]:
        """
        Global reoptimization upon vehicle breakdown.
        If offline, fails because central cloud is unreachable.
        """
        if not self.can_communicate(fleet_state):
            # Communication severed; central dispatcher cannot command the fleet
            return None

        # When online, central server runs global reoptimizer
        recovery = self.reoptimizer.recover_global(
            fleet=fleet_state,
            failed_vehicle_id=broken_vehicle_id,
            road_network=road_network,
            time_limit_sec=10,
        )
        self.total_reoptimizations += 1
        self.last_replan_timestamp = current_time_mins
        return recovery.optimization_result
