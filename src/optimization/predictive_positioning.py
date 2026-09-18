from __future__ import annotations
import math
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

from src.models.fleet_state import FleetState
from src.models.vehicle import Vehicle, VehicleStatus
from src.models.order import Order, OrderStatus
from src.models.road import RoadNetwork
from src.prediction.demand import DemandPredictor


class ZoneForecast:
    """Represents demand forecasting for a spatial geographic zone."""
    def __init__(self, zone_id: int, center: Tuple[float, float], predicted_demand: float) -> None:
        self.zone_id = zone_id
        self.center = center
        self.predicted_demand = predicted_demand


class PredictiveFleetPositioner:
    """
    Proactive AI Fleet Positioning Engine.
    Uses DemandPredictor to forecast future customer order hot-spots across zones,
    and positions idle or low-utilization commercial trucks proactively ahead of demand spikes.
    """
    def __init__(
        self,
        demand_predictor: Optional[DemandPredictor] = None,
        num_zones: int = 4,
        seed: int = 42,
    ) -> None:
        self.demand_predictor = demand_predictor or DemandPredictor(random_state=seed)
        self.num_zones = num_zones
        self.zone_centroids: Dict[int, Tuple[float, float]] = {}
        self._initialize_zone_centroids()

    def _initialize_zone_centroids(self, area_bounds: Tuple[float, float, float, float] = (0.0, 0.0, 100.0, 100.0)) -> None:
        """Divides delivery territory into representative zone centroids."""
        min_x, min_y, max_x, max_y = area_bounds
        mid_x = (min_x + max_x) / 2.0
        mid_y = (min_y + max_y) / 2.0
        # 4 quadrant centroids
        self.zone_centroids = {
            0: ((min_x + mid_x) / 2.0, (min_y + mid_y) / 2.0),  # SW
            1: ((mid_x + max_x) / 2.0, (min_y + mid_y) / 2.0),  # SE
            2: ((min_x + mid_x) / 2.0, (mid_y + max_y) / 2.0),  # NW
            3: ((mid_x + max_x) / 2.0, (mid_y + max_y) / 2.0),  # NE
        }

    def forecast_zone_demands(
        self,
        current_time_mins: float,
        day_of_week: int = 2,
        orders: Optional[List[Order]] = None,
    ) -> List[ZoneForecast]:
        """
        Queries DemandPredictor for next-period forecasted demand per zone.
        Separates predicted values from actual ground-truth arrivals.
        """
        hour_slot = int((current_time_mins / 60.0) % 24)
        # Runtime forecasts are based on actual released simulation orders,
        # aggregated spatially rather than on fixed illustrative zone values.
        # Synthetic generators remain training-data utilities only.
        order_stream = list(orders or [])
        zone_counts = {zone_id: 0.0 for zone_id in self.zone_centroids}
        recent_counts = {zone_id: 0.0 for zone_id in self.zone_centroids}
        for order in order_stream:
            if order.release_time > current_time_mins:
                continue
            zone_id = self._zone_for_coordinate(order.destination)
            zone_counts[zone_id] += 1.0
            if order.release_time >= current_time_mins - 60.0:
                recent_counts[zone_id] += 1.0
        forecasts = []

        for z_id, centroid in self.zone_centroids.items():
            if self.demand_predictor.is_trained:
                observed_count = zone_counts[z_id]
                recent_count = recent_counts[z_id]
                feat = np.array([[
                    z_id,
                    day_of_week,
                    hour_slot,
                    observed_count,
                    recent_count,
                    np.sin(2 * np.pi * (current_time_mins / 1440.0) / 365.0),
                    np.cos(2 * np.pi * (current_time_mins / 1440.0) / 365.0),
                ]])
                pred_val = float(self.demand_predictor.predict(feat)[0])
            else:
                # An untrained model may not claim a forecast.  The only
                # usable signal is the observed current stream.
                pred_val = recent_counts[z_id]

            forecasts.append(ZoneForecast(zone_id=z_id, center=centroid, predicted_demand=round(pred_val, 2)))

        # Sort zones by descending forecasted demand intensity
        forecasts.sort(key=lambda z: z.predicted_demand, reverse=True)
        return forecasts

    def _zone_for_coordinate(self, coordinate: Tuple[float, float]) -> int:
        """Return the quadrant whose centroid is closest to a simulation point."""
        return min(
            self.zone_centroids,
            key=lambda zone_id: math.hypot(
                coordinate[0] - self.zone_centroids[zone_id][0],
                coordinate[1] - self.zone_centroids[zone_id][1],
            ),
        )

    def plan_repositioning(
        self,
        fleet_state: FleetState,
        road_network: RoadNetwork,
        current_time_mins: float,
        day_of_week: int = 2,
    ) -> List[Dict[str, Any]]:
        """
        Evaluates idle trucks and assigns proactive movement towards high-demand zone centroids.
        """
        forecasts = self.forecast_zone_demands(
            current_time_mins,
            day_of_week,
            list(fleet_state.active_orders.values()),
        )
        if not forecasts:
            return []

        # Find idle or low-capacity trucks
        idle_trucks = [
            v for v in fleet_state.vehicles.values()
            if v.status == VehicleStatus.IDLE and v.current_load < 0.1 * v.max_weight
        ]

        reposition_plans = []
        # Assign highest predicted demand zone to closest available idle truck
        for forecast in forecasts[:len(idle_trucks)]:
            if not idle_trucks:
                break

            target_center = forecast.center
            # Find closest idle truck to this high-demand zone
            best_truck = min(
                idle_trucks,
                key=lambda t: math.hypot(
                    t.current_location[0] - target_center[0],
                    t.current_location[1] - target_center[1],
                ),
            )
            idle_trucks.remove(best_truck)

            # Map target coordinate to closest node in road network
            closest_node = min(
                road_network.node_coordinates.keys(),
                key=lambda n: math.hypot(
                    road_network.node_coordinates[n][0] - target_center[0],
                    road_network.node_coordinates[n][1] - target_center[1],
                ),
            )

            reposition_plans.append({
                "vehicle_id": best_truck.vehicle_id,
                "target_zone": forecast.zone_id,
                "predicted_demand": forecast.predicted_demand,
                "target_node": closest_node,
                "target_coordinates": target_center,
            })

        return reposition_plans
