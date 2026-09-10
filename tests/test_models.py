import pytest
from src.models.order import Order, OrderStatus
from src.models.vehicle import Vehicle, VehicleStatus
from src.models.road import Road, RoadNetwork, RoadStatus, TrafficLevel
from src.models.fleet_state import FleetState, ConnectivityState


def test_order_creation_and_lateness():
    order = Order(
        order_id="ORD_001",
        pickup_location=(0.0, 0.0),
        destination=(10.0, 20.0),
        demand_weight=25.0,
        volume=5.0,
        priority=2,
        earliest_delivery=100.0,
        latest_delivery=200.0,
        service_time=15.0,
    )
    assert order.order_id == "ORD_001"
    assert not order.is_late(150.0)
    assert order.lateness(150.0) == 0.0

    assert order.is_late(210.0)
    assert order.lateness(210.0) == 10.0


def test_order_invalid_time_window():
    with pytest.raises(ValueError):
        Order(
            order_id="ORD_INV",
            pickup_location=(0.0, 0.0),
            destination=(1.0, 1.0),
            demand_weight=10.0,
            earliest_delivery=100.0,
            latest_delivery=50.0,  # Invalid: latest < earliest
        )


def test_vehicle_capacity_and_loading():
    truck = Vehicle(
        vehicle_id="TRUCK_01",
        vehicle_type="heavy_duty",
        max_weight=200.0,
        max_volume=50.0,
    )
    assert truck.remaining_weight_capacity() == 200.0
    assert truck.remaining_volume_capacity() == 50.0
    assert truck.can_load(weight=150.0, volume=30.0)

    # Load order 1
    success = truck.load_order("ORD_1", weight=150.0, volume=30.0)
    assert success is True
    assert truck.current_load == 150.0
    assert truck.current_volume_load == 30.0

    # Overload attempt
    assert not truck.can_load(weight=60.0, volume=5.0)
    assert truck.load_order("ORD_2", weight=60.0, volume=5.0) is False

    # Reset
    truck.reset_load()
    assert truck.current_load == 0.0
    assert len(truck.assigned_orders) == 0


def test_road_traffic_dynamics():
    road = Road(
        road_id="R1",
        source="A",
        destination="B",
        distance=50.0,
        speed_limit=50.0,
        current_speed=50.0,
    )
    assert road.travel_time == 1.0  # 50 km / 50 km/h = 1.0 hr

    # Congestion update
    road.update_traffic(TrafficLevel.HEAVY)
    assert road.traffic_level == TrafficLevel.HEAVY
    assert road.status == RoadStatus.CONGESTED
    assert road.current_speed < 50.0
    assert road.travel_time > 1.0

    # Blocked
    road.update_traffic(TrafficLevel.BLOCKED)
    assert road.status == RoadStatus.CLOSED


def test_fleet_state_utilization():
    v1 = Vehicle(vehicle_id="V1", max_weight=100.0, current_load=50.0)
    v2 = Vehicle(vehicle_id="V2", max_weight=100.0, current_load=30.0)
    state = FleetState(
        timestamp=0.0,
        vehicles={"V1": v1, "V2": v2},
        connectivity_state=ConnectivityState.CLOUD_MODE,
    )
    assert state.total_fleet_capacity() == 200.0
    assert state.total_fleet_load() == 80.0
    assert state.fleet_utilization() == 40.0
