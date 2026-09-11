import math
import pytest
from typing import Dict, Tuple

from src.models.order import Order, OrderStatus
from src.models.vehicle import Vehicle, VehicleStatus
from src.models.road import RoadNetwork
from src.models.fleet_state import FleetState, ConnectivityState
from src.agents.truck_agent import TruckAgent
from src.agents.fleet_agent import FleetAgent, select_winning_bid
from src.networking.mesh import MeshNetwork
from src.networking.messages import MeshMessage, MessageType
from src.simulation.environment import FleetSimulationEnvironment
from src.evaluation.metrics import calculate_average_delivery_delay
from src.evaluation.scenario_generator import generate_benchmark_scenario


def _create_sample_road_and_order():
    road = RoadNetwork()
    road.add_node(0, x=0.0, y=0.0)
    road.add_node(1, x=10.0, y=0.0)
    road.add_node(2, x=20.0, y=0.0)
    node_coords = {0: (0.0, 0.0), 1: (10.0, 0.0), 2: (20.0, 0.0)}
    order = Order(
        order_id="ORD_TEST_01",
        pickup_location=(0.0, 0.0),
        destination=(10.0, 0.0),
        demand_weight=20.0,
        earliest_delivery=0.0,
        latest_delivery=120.0,
        service_time=10.0,
        status=OrderStatus.PENDING,
    )
    return road, node_coords, order


def test_A_valid_bid():
    """A. Valid bid structure containing all required keys and valid data types."""
    _, node_coords, order = _create_sample_road_and_order()
    v = Vehicle(
        vehicle_id="TRUCK_02",
        max_weight=100.0,
        current_location=(5.0, 0.0),
        current_route=[0, 0],
        current_load=10.0,
        status=VehicleStatus.IDLE,
    )
    agent = TruckAgent(vehicle_id="TRUCK_02", initial_vehicle=v)
    
    sos_msg = MeshMessage(
        message_id="SOS_01",
        message_type=MessageType.BREAKDOWN_ALERT,
        sender_id="TRUCK_01",
        receiver_id="TRUCK_02",
        timestamp_mins=10.0,
        payload={
            "orders": [order.model_dump()],
            "order_nodes": {order.order_id: 1},
        },
    )
    bids = agent.generate_bids_for_breakdown(sos_msg, node_coords)
    assert len(bids) == 1
    
    payload = bids[0].payload
    # Strict contract check: all 6 required fields must exist
    assert "order_id" in payload and payload["order_id"] == "ORD_TEST_01"
    assert "bidder_vehicle_id" in payload and payload["bidder_vehicle_id"] == "TRUCK_02"
    assert "detour_km" in payload and isinstance(payload["detour_km"], (int, float))
    assert "additional_fuel" in payload and isinstance(payload["additional_fuel"], (int, float))
    assert "additional_co2" in payload and isinstance(payload["additional_co2"], (int, float))
    assert "capacity_remaining" in payload and isinstance(payload["capacity_remaining"], (int, float))
    assert payload["capacity_remaining"] == pytest.approx(70.0, abs=1e-2)  # 100 max - (10 load + 20 order)


def test_B_bidder_vehicle_id_correctness():
    """B. bidder_vehicle_id must originate from the actual bidding vehicle, never from sender or constant."""
    _, node_coords, order = _create_sample_road_and_order()
    v = Vehicle(
        vehicle_id="TRUCK_BIDDER_X",
        max_weight=100.0,
        current_location=(5.0, 0.0),
        current_route=[0, 0],
        current_load=0.0,
        status=VehicleStatus.IDLE,
    )
    agent = TruckAgent(vehicle_id="TRUCK_BIDDER_X", initial_vehicle=v)
    
    sos_msg = MeshMessage(
        message_id="SOS_01",
        message_type=MessageType.BREAKDOWN_ALERT,
        sender_id="TRUCK_FAILED_Y",
        receiver_id="TRUCK_BIDDER_X",
        timestamp_mins=10.0,
        payload={
            "orders": [order.model_dump()],
            "order_nodes": {order.order_id: 1},
        },
    )
    bids = agent.generate_bids_for_breakdown(sos_msg, node_coords)
    assert bids[0].payload["bidder_vehicle_id"] == "TRUCK_BIDDER_X"
    assert bids[0].payload["bidder_vehicle_id"] != "TRUCK_FAILED_Y"


def test_C_multiple_bids():
    """C. System correctly receives and processes multiple bids for the same order."""
    bids = [
        {"order_id": "ORD_01", "bidder_vehicle_id": "T1", "detour_km": 15.0, "additional_fuel": 3.0, "additional_co2": 7.9, "capacity_remaining": 50.0},
        {"order_id": "ORD_01", "bidder_vehicle_id": "T2", "detour_km": 8.0, "additional_fuel": 1.6, "additional_co2": 4.2, "capacity_remaining": 30.0},
        {"order_id": "ORD_01", "bidder_vehicle_id": "T3", "detour_km": 12.0, "additional_fuel": 2.4, "additional_co2": 6.3, "capacity_remaining": 40.0},
    ]
    winner = select_winning_bid(bids, order_id="ORD_01")
    assert winner is not None
    assert winner["bidder_vehicle_id"] == "T2"


def test_D_deterministic_winner_selection():
    """D. Winner selection is strictly deterministic and invariant to bid list ordering."""
    bids_a = [
        {"order_id": "ORD_01", "bidder_vehicle_id": "T_HIGH", "detour_km": 20.0, "additional_fuel": 4.0, "additional_co2": 10.5, "capacity_remaining": 50.0},
        {"order_id": "ORD_01", "bidder_vehicle_id": "T_LOW", "detour_km": 5.0, "additional_fuel": 1.0, "additional_co2": 2.6, "capacity_remaining": 50.0},
    ]
    bids_b = list(reversed(bids_a))
    
    winner_a = select_winning_bid(bids_a, order_id="ORD_01")
    winner_b = select_winning_bid(bids_b, order_id="ORD_01")
    assert winner_a["bidder_vehicle_id"] == "T_LOW"
    assert winner_b["bidder_vehicle_id"] == "T_LOW"


def test_E_tie_breaking():
    """E. Tie-breaking deterministically selects the lexicographically smaller vehicle_id on identical metrics."""
    bids = [
        {"order_id": "ORD_01", "bidder_vehicle_id": "TRUCK_Z", "detour_km": 10.0, "additional_fuel": 2.0, "additional_co2": 5.2, "capacity_remaining": 40.0},
        {"order_id": "ORD_01", "bidder_vehicle_id": "TRUCK_A", "detour_km": 10.0, "additional_fuel": 2.0, "additional_co2": 5.2, "capacity_remaining": 40.0},
        {"order_id": "ORD_01", "bidder_vehicle_id": "TRUCK_M", "detour_km": 10.0, "additional_fuel": 2.0, "additional_co2": 5.2, "capacity_remaining": 40.0},
    ]
    winner = select_winning_bid(bids, order_id="ORD_01")
    assert winner["bidder_vehicle_id"] == "TRUCK_A"


def test_F_insufficient_capacity():
    """F. Vehicle with insufficient remaining capacity cannot absorb order or submit valid bid."""
    _, node_coords, order = _create_sample_road_and_order()
    # Order demand is 20.0, truck max is 50.0 and current load is 40.0 (only 10.0 capacity left)
    v = Vehicle(
        vehicle_id="TRUCK_FULL",
        max_weight=50.0,
        current_location=(5.0, 0.0),
        current_route=[0, 0],
        current_load=40.0,
        status=VehicleStatus.IDLE,
    )
    agent = TruckAgent(vehicle_id="TRUCK_FULL", initial_vehicle=v)
    assert agent.can_absorb(order) is False
    
    sos_msg = MeshMessage(
        message_id="SOS_01",
        message_type=MessageType.BREAKDOWN_ALERT,
        sender_id="TRUCK_BROKEN",
        receiver_id="TRUCK_FULL",
        timestamp_mins=10.0,
        payload={
            "orders": [order.model_dump()],
            "order_nodes": {order.order_id: 1},
        },
    )
    bids = agent.generate_bids_for_breakdown(sos_msg, node_coords)
    assert len(bids) == 0


def test_G_broken_vehicle_cannot_bid():
    """G. Broken vehicle must not submit bids or win transfers."""
    _, node_coords, order = _create_sample_road_and_order()
    v = Vehicle(
        vehicle_id="TRUCK_DEAD",
        max_weight=100.0,
        current_location=(5.0, 0.0),
        current_route=[0, 0],
        current_load=0.0,
        status=VehicleStatus.BROKEN_DOWN,
    )
    agent = TruckAgent(vehicle_id="TRUCK_DEAD", initial_vehicle=v)
    assert agent.can_absorb(order) is False
    
    sos_msg = MeshMessage(
        message_id="SOS_01",
        message_type=MessageType.BREAKDOWN_ALERT,
        sender_id="TRUCK_OTHER",
        receiver_id="TRUCK_DEAD",
        timestamp_mins=10.0,
        payload={
            "orders": [order.model_dump()],
            "order_nodes": {order.order_id: 1},
        },
    )
    bids = agent.generate_bids_for_breakdown(sos_msg, node_coords)
    assert len(bids) == 0
    
    # Also verify select_winning_bid filters out broken truck even if bid was injected
    bad_bid = [{"order_id": "ORD_TEST_01", "bidder_vehicle_id": "TRUCK_DEAD", "detour_km": 1.0, "additional_fuel": 0.2, "additional_co2": 0.5, "capacity_remaining": 50.0}]
    winner = select_winning_bid(bad_bid, order_id="ORD_TEST_01", truck_agents={"TRUCK_DEAD": agent})
    assert winner is None


def test_H_unreachable_vehicle_cannot_bid():
    """H. Vehicle outside mesh transmission range cannot bid or receive transfer."""
    road = RoadNetwork()
    road.add_node(0, x=0.0, y=0.0)
    road.add_node(1, x=5.0, y=0.0)
    
    ord_h = Order(order_id="ORD_H", destination=(5.0, 0.0), demand_weight=10.0, latest_delivery=100.0)
    v_broken = Vehicle(vehicle_id="V_BROKEN", max_weight=50.0, current_location=(0.0, 0.0), current_route=[0, 1, 0], assigned_orders=["ORD_H"], current_load=10.0, status=VehicleStatus.BROKEN_DOWN)
    v_far = Vehicle(vehicle_id="V_FAR", max_weight=50.0, current_location=(100.0, 0.0), current_route=[0, 0], assigned_orders=[], current_load=0.0, status=VehicleStatus.IDLE)
    
    fleet = FleetState(vehicles={"V_BROKEN": v_broken, "V_FAR": v_far}, active_orders={"ORD_H": ord_h}, road_network=road)
    mesh = MeshNetwork(transmission_range_km=10.0, packet_loss_per_hop=0.0, seed=42)
    fleet_agent = FleetAgent(fleet_state=fleet, road_network=road, mesh_network=mesh, seed=42)
    
    res = fleet_agent.on_vehicle_breakdown_decentralized("V_BROKEN", current_time_mins=5.0, node_id_map={"ORD_H": 1})
    assert res["success"] is False
    assert len(res["transfers"]) == 0
    assert "ORD_H" in fleet_agent.truck_agents["V_BROKEN"].state.assigned_orders


def test_I_order_transfer():
    """I. Successful order transfer updates from_vehicle, to_vehicle, load, and preserves metadata."""
    road = RoadNetwork()
    road.add_node(0, x=0.0, y=0.0)
    road.add_node(1, x=5.0, y=0.0)
    
    ord_i = Order(order_id="ORD_I", destination=(5.0, 0.0), demand_weight=15.0, earliest_delivery=10.0, latest_delivery=100.0, service_time=12.0)
    v_src = Vehicle(vehicle_id="V_SRC", max_weight=50.0, current_location=(0.0, 0.0), current_route=[0, 1, 0], assigned_orders=["ORD_I"], current_load=15.0, status=VehicleStatus.BROKEN_DOWN)
    v_dst = Vehicle(vehicle_id="V_DST", max_weight=50.0, current_location=(2.0, 0.0), current_route=[0, 0], assigned_orders=[], current_load=0.0, status=VehicleStatus.IDLE)
    
    fleet = FleetState(vehicles={"V_SRC": v_src, "V_DST": v_dst}, active_orders={"ORD_I": ord_i}, road_network=road)
    mesh = MeshNetwork(transmission_range_km=10.0, packet_loss_per_hop=0.0, seed=42)
    fleet_agent = FleetAgent(fleet_state=fleet, road_network=road, mesh_network=mesh, seed=42)
    
    res = fleet_agent.on_vehicle_breakdown_decentralized("V_SRC", current_time_mins=5.0, node_id_map={"ORD_I": 1})
    assert res["success"] is True
    
    # Check states
    assert "ORD_I" not in fleet_agent.truck_agents["V_SRC"].state.assigned_orders
    assert "ORD_I" in fleet_agent.truck_agents["V_DST"].state.assigned_orders
    assert fleet_agent.truck_agents["V_SRC"].state.current_load == 0.0
    assert fleet_agent.truck_agents["V_DST"].state.current_load == 15.0
    
    # Metadata preserved
    ord_obj = fleet.active_orders["ORD_I"]
    assert ord_obj.order_id == "ORD_I"
    assert ord_obj.demand_weight == 15.0
    assert ord_obj.destination == (5.0, 0.0)
    assert ord_obj.earliest_delivery == 10.0
    assert ord_obj.latest_delivery == 100.0
    assert ord_obj.service_time == 12.0
    assert ord_obj.assigned_vehicle_id == "V_DST"
    assert ord_obj.status == OrderStatus.REASSIGNED


def test_J_no_duplicate_order_after_transfer():
    """J. No duplicate orders created during transfer across fleet or route lists."""
    road = RoadNetwork()
    road.add_node(0, x=0.0, y=0.0)
    road.add_node(1, x=5.0, y=0.0)
    
    ord_j = Order(order_id="ORD_J", destination=(5.0, 0.0), demand_weight=10.0, latest_delivery=100.0)
    v1 = Vehicle(vehicle_id="V1", max_weight=50.0, current_location=(0.0, 0.0), current_route=[0, 1, 0], assigned_orders=["ORD_J"], current_load=10.0, status=VehicleStatus.BROKEN_DOWN)
    v2 = Vehicle(vehicle_id="V2", max_weight=50.0, current_location=(2.0, 0.0), current_route=[0, 0], assigned_orders=[], current_load=0.0)
    
    fleet = FleetState(vehicles={"V1": v1, "V2": v2}, active_orders={"ORD_J": ord_j}, road_network=road)
    mesh = MeshNetwork(transmission_range_km=10.0, seed=42)
    fleet_agent = FleetAgent(fleet_state=fleet, road_network=road, mesh_network=mesh, seed=42)
    
    fleet_agent.on_vehicle_breakdown_decentralized("V1", current_time_mins=5.0, node_id_map={"ORD_J": 1})
    
    # Count occurrences across all vehicle assigned_orders
    all_assigned = []
    for v in fleet.vehicles.values():
        all_assigned.extend(v.assigned_orders)
    assert all_assigned.count("ORD_J") == 1
    
    # Count occurrences in agent assigned_orders
    agent_assigned = []
    for a in fleet_agent.truck_agents.values():
        agent_assigned.extend(a.state.assigned_orders)
    assert agent_assigned.count("ORD_J") == 1


def test_K_broken_truck_stops_moving():
    """K. Broken vehicle freezes spatial position and edge progress."""
    from src.models.road import Road
    road = RoadNetwork()
    road.add_node(0, x=0.0, y=0.0)
    road.add_node(1, x=20.0, y=0.0)
    road.add_road(Road(road_id="R01", source=0, destination=1, distance=20.0))
    road.add_road(Road(road_id="R10", source=1, destination=0, distance=20.0))
    
    v = Vehicle(vehicle_id="TRUCK_K", max_weight=50.0, current_location=(0.0, 0.0), current_route=[0, 1, 0], assigned_orders=[], current_load=0.0)
    fleet = FleetState(vehicles={"TRUCK_K": v}, active_orders={}, road_network=road)
    
    env = FleetSimulationEnvironment(fleet_state=fleet, road_network=road, node_id_map={}, step_size_mins=1.0)
    # Advance 5 steps while operational
    for _ in range(5):
        env.step()
    pos_before_breakdown = fleet.vehicles["TRUCK_K"].current_location
    progress_before = fleet.vehicles["TRUCK_K"].edge_progress_km
    assert progress_before > 0.0
    
    # Trigger breakdown
    fleet.vehicles["TRUCK_K"].status = VehicleStatus.BROKEN_DOWN
    
    # Advance 10 more steps: vehicle must NOT move
    for _ in range(10):
        env.step()
    assert fleet.vehicles["TRUCK_K"].current_location == pos_before_breakdown
    assert fleet.vehicles["TRUCK_K"].edge_progress_km == progress_before


def test_L_broken_truck_cannot_deliver():
    """L. Broken vehicle cannot deliver orders or complete deliveries."""
    from src.models.road import Road
    road = RoadNetwork()
    road.add_node(0, x=0.0, y=0.0)
    road.add_node(1, x=1.0, y=0.0)
    road.add_road(Road(road_id="R01", source=0, destination=1, distance=1.0))
    road.add_road(Road(road_id="R10", source=1, destination=0, distance=1.0))
    
    ord_l = Order(order_id="ORD_L", destination=(1.0, 0.0), demand_weight=5.0, latest_delivery=50.0)
    v = Vehicle(vehicle_id="TRUCK_L", max_weight=50.0, current_location=(0.0, 0.0), current_route=[0, 1, 0], assigned_orders=["ORD_L"], current_load=5.0)
    fleet = FleetState(vehicles={"TRUCK_L": v}, active_orders={"ORD_L": ord_l}, road_network=road)
    
    env = FleetSimulationEnvironment(fleet_state=fleet, road_network=road, node_id_map={"ORD_L": 1}, step_size_mins=1.0)
    # Immediately break truck down at t=0
    fleet.vehicles["TRUCK_L"].status = VehicleStatus.BROKEN_DOWN
    
    for _ in range(20):
        env.step()
    
    assert "ORD_L" not in env.delivered_orders
    assert ord_l.status != OrderStatus.DELIVERED


def test_M_mesh_direct_communication():
    """M. Single-hop direct peer-to-peer transmission within range."""
    mesh = MeshNetwork(transmission_range_km=15.0, packet_loss_per_hop=0.0, seed=42)
    mesh.update_node_position("N1", (0.0, 0.0))
    mesh.update_node_position("N2", (10.0, 0.0))
    
    msg = MeshMessage(
        message_id="MSG_M",
        message_type=MessageType.HEARTBEAT,
        sender_id="N1",
        receiver_id="N2",
        timestamp_mins=0.0,
    )
    ok = mesh.transmit(msg)
    assert ok is True
    assert msg.delivered is True
    assert msg.hop_count == 1
    assert msg.route_taken == ["N1", "N2"]


def test_N_mesh_multi_hop_communication():
    """N. Multi-hop mesh routing over intermediary node."""
    mesh = MeshNetwork(transmission_range_km=15.0, packet_loss_per_hop=0.0, seed=42)
    # N1 and N3 are 24 km apart (out of single hop 15km range), but N2 is at 12km
    mesh.update_node_position("N1", (0.0, 0.0))
    mesh.update_node_position("N2", (12.0, 0.0))
    mesh.update_node_position("N3", (24.0, 0.0))
    
    msg = MeshMessage(
        message_id="MSG_N",
        message_type=MessageType.HEARTBEAT,
        sender_id="N1",
        receiver_id="N3",
        timestamp_mins=0.0,
    )
    ok = mesh.transmit(msg)
    assert ok is True
    assert msg.delivered is True
    assert msg.hop_count == 2
    assert msg.route_taken == ["N1", "N2", "N3"]


def test_O_disconnected_vehicle_behavior():
    """O. Disconnected vehicle cannot transmit or participate in mesh recovery."""
    mesh = MeshNetwork(transmission_range_km=10.0, packet_loss_per_hop=0.0, seed=42)
    mesh.update_node_position("ONLINE_A", (0.0, 0.0))
    mesh.update_node_position("DISCONNECTED_B", (5.0, 0.0))
    mesh.set_node_failed("DISCONNECTED_B", failed=True)
    
    msg = MeshMessage(
        message_id="MSG_O",
        message_type=MessageType.HEARTBEAT,
        sender_id="ONLINE_A",
        receiver_id="DISCONNECTED_B",
        timestamp_mins=0.0,
    )
    ok = mesh.transmit(msg)
    assert ok is False
    assert msg.delivered is False


def test_P_actual_mesh_packet_failure():
    """P. Packet loss occurs and is handled correctly without fake success flags."""
    mesh = MeshNetwork(transmission_range_km=20.0, packet_loss_per_hop=1.0, seed=42)  # 100% loss
    mesh.update_node_position("P1", (0.0, 0.0))
    mesh.update_node_position("P2", (10.0, 0.0))
    
    msg = MeshMessage(
        message_id="MSG_P",
        message_type=MessageType.HEARTBEAT,
        sender_id="P1",
        receiver_id="P2",
        timestamp_mins=0.0,
    )
    ok = mesh.transmit(msg, max_retries=1)
    assert ok is False
    assert msg.delivered is False
    
    metrics = mesh.get_mesh_metrics()
    assert metrics["total_messages"] == 1
    assert metrics["delivered_messages"] == 0
    assert metrics["delivery_success"] is False
    assert metrics["delivery_success_rate"] == 0.0


def test_Q_correct_average_delay():
    """Q. Average delivery delay divides strictly by delayed orders count."""
    orders = [
        Order(order_id="O1", destination=(0, 0), demand_weight=1, latest_delivery=10.0, actual_delivery_time=25.0, status=OrderStatus.DELIVERED), # delay 15
        Order(order_id="O2", destination=(0, 0), demand_weight=1, latest_delivery=10.0, actual_delivery_time=35.0, status=OrderStatus.DELIVERED), # delay 25
        Order(order_id="O3", destination=(0, 0), demand_weight=1, latest_delivery=50.0, actual_delivery_time=40.0, status=OrderStatus.DELIVERED), # on-time (0 delay)
        Order(order_id="O4", destination=(0, 0), demand_weight=1, latest_delivery=50.0, actual_delivery_time=45.0, status=OrderStatus.DELIVERED), # on-time (0 delay)
    ]
    avg_delay = calculate_average_delivery_delay(orders)
    # Total delay = 15 + 25 = 40. Count of delayed = 2. Delay = 20.0 (NOT 40 / 4 = 10.0)
    assert avg_delay == pytest.approx(20.0, abs=1e-3)


def test_R_no_artificial_failed_order_manipulation():
    """R. Failed orders in environment metrics strictly reflects unserved orders without artificial offset."""
    road = RoadNetwork()
    road.add_node(0, x=0.0, y=0.0)
    road.add_node(1, x=5.0, y=0.0)
    
    ord_r1 = Order(order_id="R1", destination=(5.0, 0.0), demand_weight=5.0, latest_delivery=50.0)
    ord_r2 = Order(order_id="R2", destination=(5.0, 0.0), demand_weight=5.0, latest_delivery=50.0)
    v = Vehicle(vehicle_id="V_R", max_weight=50.0, current_location=(0.0, 0.0), current_route=[0, 0], assigned_orders=[], current_load=0.0, status=VehicleStatus.IDLE)
    
    fleet = FleetState(vehicles={"V_R": v}, active_orders={"R1": ord_r1, "R2": ord_r2}, road_network=road)
    env = FleetSimulationEnvironment(fleet_state=fleet, road_network=road, node_id_map={"R1": 1, "R2": 1}, step_size_mins=1.0)
    
    # 0 deliveries executed
    metrics = env.get_metrics()
    assert metrics["completed_deliveries"] == 0
    assert metrics["failed_orders"] == 2
    assert metrics["total_orders"] == 2
    assert metrics["failed_orders"] + metrics["completed_deliveries"] == metrics["total_orders"]


def test_S_identical_scenario_generation_from_identical_seed():
    """S. Common scenario generator produces perfectly identical initial fleet, orders, and disruption events for identical seeds."""
    scen_a = generate_benchmark_scenario(seed=12345, dataset_name="C101", customers_count=20, vehicles_count=4)
    scen_b = generate_benchmark_scenario(seed=12345, dataset_name="C101", customers_count=20, vehicles_count=4)
    
    # Identical fleet
    fleet_a = scen_a.get_fleet_copy()
    fleet_b = scen_b.get_fleet_copy()
    assert set(fleet_a.vehicles.keys()) == set(fleet_b.vehicles.keys())
    for v_id in fleet_a.vehicles:
        assert fleet_a.vehicles[v_id].max_weight == fleet_b.vehicles[v_id].max_weight
        assert fleet_a.vehicles[v_id].current_location == fleet_b.vehicles[v_id].current_location
    
    # Identical orders
    orders_a = scen_a.get_orders_list()
    orders_b = scen_b.get_orders_list()
    assert len(orders_a) == len(orders_b)
    for oa, ob in zip(orders_a, orders_b):
        assert oa.order_id == ob.order_id
        assert oa.demand_weight == ob.demand_weight
        assert oa.destination == ob.destination
        assert oa.latest_delivery == ob.latest_delivery
    
    # Identical disruptions
    brk_a = scen_a.get_breakdown_spec()
    brk_b = scen_b.get_breakdown_spec()
    assert brk_a.timestamp_mins == brk_b.timestamp_mins
    assert brk_a.payload["vehicle_id"] == brk_b.payload["vehicle_id"]
