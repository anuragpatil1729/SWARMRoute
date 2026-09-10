import pytest
from src.data.loaders.solomon import load_solomon_benchmark
from src.models.vehicle import VehicleStatus
from src.optimization.dynamic_reoptimizer import DynamicReoptimizer


def test_local_recovery_after_breakdown():
    fleet, network, meta = load_solomon_benchmark("C101", max_customers=25, vehicle_count=5)
    orders = list(fleet.active_orders.values())
    node_id_map = {o.order_id: idx + 1 for idx, o in enumerate(orders)}

    # Manually assign orders across vehicles
    v_ids = list(fleet.vehicles.keys())
    fleet.vehicles[v_ids[0]].current_route = [0, 1, 2, 3, 0]
    fleet.vehicles[v_ids[0]].assigned_orders = ["ORD_001", "ORD_002", "ORD_003"]

    fleet.vehicles[v_ids[1]].current_route = [0, 4, 5, 0]
    fleet.vehicles[v_ids[1]].assigned_orders = ["ORD_004", "ORD_005"]

    fleet.vehicles[v_ids[2]].current_route = [0, 6, 7, 0]
    fleet.vehicles[v_ids[2]].assigned_orders = ["ORD_006", "ORD_007"]

    # Truck 0 breaks down
    reoptimizer = DynamicReoptimizer()
    res = reoptimizer.recover_local(
        fleet_state=fleet,
        broken_vehicle_id=v_ids[0],
        road_network=network,
        node_id_map=node_id_map,
        current_time_mins=30.0,
    )

    assert res.strategy == "LOCAL_RECOVERY"
    assert res.orders_recovered == 3
    assert res.orders_failed == 0
    assert res.recovery_time_sec < 1.0  # Peer exchange executes in milliseconds

    # Verify stranded orders were moved to other operational trucks
    all_assigned = []
    for vid, v in fleet.vehicles.items():
        if vid != v_ids[0]:
            all_assigned.extend(v.assigned_orders)
    for oid in ["ORD_001", "ORD_002", "ORD_003"]:
        assert oid in all_assigned
