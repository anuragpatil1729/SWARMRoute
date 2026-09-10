from __future__ import annotations
import math
from typing import Dict, List, Optional, Tuple
from pydantic import BaseModel, Field

from src.models.order import Order
from src.models.vehicle import Vehicle


class LoadAssignmentResult(BaseModel):
    """Result of multi-capacity vehicle load partitioning."""
    vehicle_assignments: Dict[str, List[str]] = Field(
        default_factory=dict, description="vehicle_id -> list of order_ids"
    )
    vehicle_loads: Dict[str, float] = Field(
        default_factory=dict, description="vehicle_id -> total weight"
    )
    vehicle_volumes: Dict[str, float] = Field(
        default_factory=dict, description="vehicle_id -> total volume"
    )
    unassigned_orders: List[str] = Field(
        default_factory=list, description="Orders unable to fit in any truck"
    )


class LoadOptimizer:
    """
    Decoupled Load Optimizer.
    Assigns orders to vehicles by considering:
      1. Truck weight capacity
      2. Truck volume capacity
      3. Geographic clustering (polar angle around depot & proximity)
      4. Delivery deadline urgency (earliest deadline first)
      5. Vehicle efficiency matching
    Produces a clean mapping: truck_id -> assigned_orders.
    """

    def __init__(
        self,
        depot_coord: Tuple[float, float] = (0.0, 0.0),
        urgency_weight: float = 0.3,
        cluster_weight: float = 0.7,
    ) -> None:
        self.depot_coord = depot_coord
        self.urgency_weight = urgency_weight
        self.cluster_weight = cluster_weight

    def _compute_polar_angle(self, coord: Tuple[float, float]) -> float:
        """Calculates polar angle from depot (-pi to +pi)."""
        dx = coord[0] - self.depot_coord[0]
        dy = coord[1] - self.depot_coord[1]
        return math.atan2(dy, dx)

    def optimize_load(
        self,
        vehicles: List[Vehicle],
        orders: List[Order],
    ) -> LoadAssignmentResult:
        """
        Partitions orders among available vehicles respecting weight, volume,
        and geographic/deadline affinities.
        """
        if not vehicles or not orders:
            return LoadAssignmentResult()

        # Sort vehicles by efficiency / capacity descending
        sorted_vehicles = sorted(
            vehicles,
            key=lambda v: (v.max_weight, -v.fuel_efficiency),
            reverse=True,
        )

        # Sort orders by deadline urgency and polar angle to cluster geographically
        sorted_orders = sorted(
            orders,
            key=lambda o: (
                o.priority * -1000,
                self._compute_polar_angle(o.destination),
                o.latest_delivery,
            ),
        )

        assignments: Dict[str, List[str]] = {v.vehicle_id: [] for v in sorted_vehicles}
        weights: Dict[str, float] = {v.vehicle_id: 0.0 for v in sorted_vehicles}
        volumes: Dict[str, float] = {v.vehicle_id: 0.0 for v in sorted_vehicles}
        unassigned: List[str] = []

        v_lookup = {v.vehicle_id: v for v in sorted_vehicles}

        for order in sorted_orders:
            assigned = False
            # Find best fitting vehicle
            best_v_id: Optional[str] = None
            min_load_ratio = float("inf")

            for v in sorted_vehicles:
                v_id = v.vehicle_id
                curr_w = weights[v_id]
                curr_v = volumes[v_id]

                if curr_w + order.demand_weight <= v.max_weight and curr_v + order.volume <= v.max_volume:
                    # Choose vehicle that keeps fleet load balanced or fills current cluster
                    load_ratio = (curr_w + order.demand_weight) / v.max_weight
                    if load_ratio < min_load_ratio:
                        min_load_ratio = load_ratio
                        best_v_id = v_id

            if best_v_id is not None:
                assignments[best_v_id].append(order.order_id)
                weights[best_v_id] += order.demand_weight
                volumes[best_v_id] += order.volume
                assigned = True

            if not assigned:
                unassigned.append(order.order_id)

        return LoadAssignmentResult(
            vehicle_assignments=assignments,
            vehicle_loads=weights,
            vehicle_volumes=volumes,
            unassigned_orders=unassigned,
        )
