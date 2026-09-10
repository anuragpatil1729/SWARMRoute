import pytest
from pathlib import Path
from src.data.loaders.solomon import load_solomon_benchmark
from src.optimization.route_optimizer import RouteOptimizer
from src.optimization.load_optimizer import LoadOptimizer


def test_load_optimizer_capacity_bounds():
    solomon_path = Path("data/raw/solomon/C101.txt")
    if not solomon_path.exists():
        pytest.skip("Solomon C101.txt not found locally")

    fleet, network, meta = load_solomon_benchmark("C101", max_customers=25, vehicle_count=5)
    load_opt = LoadOptimizer(depot_coord=meta["depot_coord"])
    alloc = load_opt.optimize_load(
        vehicles=list(fleet.vehicles.values()),
        orders=list(fleet.active_orders.values()),
    )

    # Verify no truck exceeds capacity
    for v_id, total_w in alloc.vehicle_loads.items():
        truck = fleet.vehicles[v_id]
        assert total_w <= truck.max_weight, f"Truck {v_id} exceeded capacity: {total_w} > {truck.max_weight}"

    # Verify all orders partitioned
    total_assigned = sum(len(ords) for ords in alloc.vehicle_assignments.values())
    assert total_assigned + len(alloc.unassigned_orders) == 25


def test_ortools_cvrptw_c101_constraints():
    solomon_path = Path("data/raw/solomon/C101.txt")
    if not solomon_path.exists():
        pytest.skip("Solomon C101.txt not found locally")

    fleet, network, meta = load_solomon_benchmark("C101", max_customers=25, vehicle_count=10)
    optimizer = RouteOptimizer()
    result = optimizer.optimize(
        fleet=fleet,
        orders=fleet.active_orders,
        road_network=network,
        time_limit_sec=5,
    )

    assert result.status in ("OPTIMAL", "FEASIBLE")
    assert result.late_deliveries_count == 0, "Expected 0 late deliveries on C101 25-customer instance"
    assert len(result.unassigned_orders) == 0, "All 25 orders should be fulfilled"
    assert result.total_distance > 0
    assert result.total_fuel > 0
    assert result.total_emissions > 0
    assert result.active_vehicles_count > 0

    # Strict check: Validate capacity constraints for every vehicle
    for v_id, route in result.routes.items():
        if len(route) <= 2:
            continue
        route_demand = sum(
            network.graph.nodes[node]["demand"] for node in route if node != 0
        )
        truck = fleet.vehicles[v_id]
        assert route_demand <= truck.max_weight, f"Route demand {route_demand} exceeded truck capacity {truck.max_weight}"

    # Strict check: Validate time window bounds for every stop
    for v_id, arrivals in result.arrival_times.items():
        for node_idx, arr_time in arrivals.items():
            if node_idx != 0:
                node_data = network.graph.nodes[node_idx]
                ready = node_data["ready_time"]
                due = node_data["due_date"]
                assert arr_time <= due + 1e-4, f"Stop {node_idx} arrival {arr_time} missed deadline {due}"
