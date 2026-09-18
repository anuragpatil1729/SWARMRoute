"""Regression tests for runtime (not presentation) decision integrations."""

import numpy as np

from src.models.fleet_state import FleetState
from src.models.order import Order
from src.models.road import RoadNetwork
from src.models.vehicle import Vehicle, VehicleStatus
from src.optimization.predictive_positioning import PredictiveFleetPositioner


class _ObservedDemandModel:
    """Small deterministic trained predictor used to expose runtime features."""

    is_trained = True

    def predict(self, features):
        # Feature 4 is the last-hour count created from live orders.
        return np.asarray(features)[:, 4]


def test_dynamic_orders_drive_demand_forecast_and_idle_repositioning():
    road = RoadNetwork()
    road.add_node(0, x=0.0, y=0.0)
    road.add_node(1, x=75.0, y=75.0)
    idle = Vehicle(
        vehicle_id="IDLE", max_weight=100.0, current_location=(0.0, 0.0),
        status=VehicleStatus.IDLE,
    )
    positioner = PredictiveFleetPositioner(demand_predictor=_ObservedDemandModel())

    quiet = FleetState(vehicles={"IDLE": idle}, active_orders={}, road_network=road)
    quiet_forecasts = positioner.forecast_zone_demands(60.0, orders=[])

    burst_orders = {
        f"BURST_{index}": Order(
            order_id=f"BURST_{index}", destination=(80.0, 80.0), demand_weight=1.0,
            release_time=55.0, latest_delivery=180.0,
        )
        for index in range(4)
    }
    burst = FleetState(vehicles={"IDLE": idle.model_copy(deep=True)}, active_orders=burst_orders, road_network=road)
    burst_forecasts = positioner.forecast_zone_demands(60.0, orders=list(burst_orders.values()))
    plans = positioner.plan_repositioning(burst, road, 60.0)

    assert quiet_forecasts[0].predicted_demand == 0.0
    assert burst_forecasts[0].zone_id == 3
    assert burst_forecasts[0].predicted_demand == 4.0
    assert plans[0]["vehicle_id"] == "IDLE"
    assert plans[0]["target_zone"] == 3
