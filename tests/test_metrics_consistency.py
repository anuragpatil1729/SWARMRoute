import pytest
from src.evaluation.metrics import (
    calculate_total_distance,
    calculate_total_travel_time,
    calculate_total_emissions,
    calculate_total_cost,
    calculate_late_deliveries,
    calculate_completion_rate,
    calculate_vehicle_utilization,
    FleetMetrics,
)
from src.models.order import Order
from src.models.vehicle import Vehicle


def test_metrics_functional_calculators():
    # 1. Distance
    routes = [[0, 1, 2, 0]]
    dist_map = {(0, 1): 10.0, (1, 2): 15.0, (2, 0): 20.0}
    total_d = calculate_total_distance(routes, dist_map)
    assert total_d == 45.0

    # 2. Emissions
    fuel = 50.0
    emissions = calculate_total_emissions(fuel, emission_factor_kg_per_l=2.68)
    assert emissions == round(50.0 * 2.68, 2)

    # 3. Cost
    cost = calculate_total_cost(
        distance_km=100.0,
        fuel_liters=30.0,
        delay_hours=1.5,
        emissions_kg=80.4,
        vehicles_used=2,
    )
    # distance (100*1) + fuel (30*2) + delay (1.5*10) + emissions (80.4*3) + vehicle (2*5) = 100 + 60 + 15 + 241.2 + 10 = 426.2
    assert cost == 426.2

    # 4. Late deliveries
    ord1 = Order(order_id="O1", destination=(0, 0), demand_weight=10, latest_delivery=30.0, actual_delivery_time=25.0)
    ord2 = Order(order_id="O2", destination=(0, 0), demand_weight=10, latest_delivery=30.0, actual_delivery_time=45.0)
    late_cnt, max_lat = calculate_late_deliveries([ord1, ord2])
    assert late_cnt == 1
    assert max_lat == 15.0

    # 5. Completion rate
    comp_rate = calculate_completion_rate(total_orders=100, delivered_orders=95)
    assert comp_rate == 95.0

    # 6. Utilization
    v1 = Vehicle(vehicle_id="V1", max_weight=200.0, current_load=150.0, current_route=[0, 1, 0])
    util = calculate_vehicle_utilization([v1])
    assert util == 75.0
