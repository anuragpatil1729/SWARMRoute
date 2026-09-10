import pytest
from src.models.order import Order, OrderStatus
from src.models.vehicle import Vehicle, VehicleStatus
from src.models.road import RoadNetwork, Road, TrafficLevel
from src.models.fleet_state import FleetState, ConnectivityState
from src.simulation.environment import FleetSimulationEnvironment
from src.simulation.events import FleetEvent, EventType


def create_simple_env():
    road_network = RoadNetwork()
    # Depot at (0, 0), Cust 1 at (10, 0), Cust 2 at (20, 0)
    road_network.add_node(0, x=0.0, y=0.0)
    road_network.add_node(1, x=10.0, y=0.0)
    road_network.add_node(2, x=20.0, y=0.0)

    road_network.add_road(Road(road_id="R01", source=0, destination=1, distance=10.0, speed_limit=60.0))
    road_network.add_road(Road(road_id="R12", source=1, destination=2, distance=10.0, speed_limit=60.0))
    road_network.add_road(Road(road_id="R20", source=2, destination=0, distance=20.0, speed_limit=60.0))

    ord1 = Order(
        order_id="ORD_01",
        pickup_location=(0.0, 0.0),
        destination=(10.0, 0.0),
        demand_weight=50.0,
        earliest_delivery=0.0,
        latest_delivery=30.0,
        service_time=5.0,
    )
    ord2 = Order(
        order_id="ORD_02",
        pickup_location=(0.0, 0.0),
        destination=(20.0, 0.0),
        demand_weight=40.0,
        earliest_delivery=0.0,
        latest_delivery=60.0,
        service_time=5.0,
    )

    truck = Vehicle(
        vehicle_id="TRUCK_01",
        max_weight=200.0,
        average_speed=60.0,  # 1 km per minute
        current_route=[0, 1, 2, 0],
        assigned_orders=["ORD_01", "ORD_02"],
    )

    fleet = FleetState(
        vehicles={"TRUCK_01": truck},
        active_orders={"ORD_01": ord1, "ORD_02": ord2},
        road_network=road_network,
    )
    node_map = {"ORD_01": 1, "ORD_02": 2}

    from src.simulation.traffic import TrafficSimulator
    traffic_sim = TrafficSimulator(hourly_schedule={h: TrafficLevel.NORMAL for h in range(24)})
    env = FleetSimulationEnvironment(
        fleet_state=fleet,
        road_network=road_network,
        node_id_map=node_map,
        traffic_sim=traffic_sim,
        step_size_mins=1.0,
    )
    return env, truck, ord1, ord2


def test_vehicle_edge_movement():
    env, truck, ord1, ord2 = create_simple_env()
    assert truck.status == VehicleStatus.EN_ROUTE
    assert truck.current_node == 0
    assert truck.next_node == 1
    assert truck.current_load == 90.0

    # Step 5 mins: at 60 km/h (1 km/min), moves 5 km along edge of length 10 km
    for _ in range(5):
        env.step()

    assert env.current_time_mins == 5.0
    assert truck.edge_progress_km == 5.0
    assert truck.current_location[0] == pytest.approx(5.0, abs=0.1)
    assert truck.status == VehicleStatus.EN_ROUTE


def test_delivery_completion_and_service_countdown():
    env, truck, ord1, ord2 = create_simple_env()

    # Step 10 mins: arrives at node 1 (order 1)
    for _ in range(10):
        env.step()

    assert env.current_time_mins == 10.0
    assert "ORD_01" in env.delivered_orders
    assert ord1.status == OrderStatus.DELIVERED
    assert ord1.actual_arrival_time == 10.0
    assert ord1.is_late() is False
    assert truck.current_load == pytest.approx(40.0, abs=0.1) # unloaded 50kg
    assert truck.status == VehicleStatus.DELIVERING
    assert truck.service_remaining_mins == 5.0

    # Advance 5 more mins: finishes service, begins travel to node 2
    for _ in range(5):
        env.step()

    assert truck.service_remaining_mins == 0.0
    assert truck.status == VehicleStatus.EN_ROUTE
    assert truck.current_node == 1
    assert truck.next_node == 2


def test_breakdown_stops_truck_and_fails_stranded():
    env, truck, ord1, ord2 = create_simple_env()

    # Trigger breakdown at T=5m
    env.event_engine.schedule(
        FleetEvent(
            event_id="EV_BRK",
            event_type=EventType.VEHICLE_BREAKDOWN,
            timestamp=5.0,
            payload={"vehicle_id": "TRUCK_01"},
        )
    )

    for _ in range(10):
        env.step()

    assert truck.status == VehicleStatus.BROKEN_DOWN
    # Truck halted at 4 km when breakdown fired
    assert truck.edge_progress_km == 4.0
    # Both orders failed
    assert "ORD_01" in env.failed_orders
    assert "ORD_02" in env.failed_orders
