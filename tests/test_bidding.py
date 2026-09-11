import pytest
from src.models.order import Order, OrderStatus
from src.models.vehicle import Vehicle, VehicleStatus
from src.models.road import RoadNetwork
from src.models.fleet_state import FleetState, ConnectivityState
from src.networking.mesh import MeshNetwork
from src.networking.messages import MeshMessage, MessageType
from src.agents.truck_agent import TruckAgent
from src.agents.fleet_agent import FleetAgent


def setup_bidding_scenario():
    road = RoadNetwork()
    road.add_node(0, x=0.0, y=0.0)
    road.add_node(1, x=10.0, y=0.0)
    road.add_node(2, x=20.0, y=0.0)
    road.add_node(3, x=0.0, y=30.0)

    order = Order(
        order_id="ORD_100",
        destination=(10.0, 0.0),
        demand_weight=20.0,
        latest_delivery=120.0,
        status=OrderStatus.PENDING,
    )
    node_coords = {0: (0.0, 0.0), 1: (10.0, 0.0), 2: (20.0, 0.0), 3: (0.0, 30.0)}
    node_id_map = {"ORD_100": 1}
    return road, order, node_coords, node_id_map


def test_valid_bid_structure_and_emission_tracking():
    road, order, node_coords, node_id_map = setup_bidding_scenario()
    veh = Vehicle(vehicle_id="TRUCK_A", max_weight=200.0, current_route=[0, 2, 0])
    agent = TruckAgent(vehicle_id="TRUCK_A", initial_vehicle=veh)

    sos = MeshMessage(
        message_id="SOS_T1",
        message_type=MessageType.BREAKDOWN_ALERT,
        sender_id="TRUCK_BROKEN",
        receiver_id="BROADCAST",
        timestamp_mins=0.0,
        payload={"orders": [order.model_dump()], "order_nodes": {"ORD_100": 1}},
    )

    bids = agent.generate_bids_for_breakdown(sos, node_coords)
    assert len(bids) == 1
    bid = bids[0].payload

    # Explicit fields required by Phase 3
    assert bid["order_id"] == "ORD_100"
    assert bid["bidder_vehicle_id"] == "TRUCK_A"
    assert "detour_km" in bid and bid["detour_km"] >= 0.0
    assert "additional_fuel" in bid and bid["additional_fuel"] >= 0.0
    assert "additional_co2" in bid and bid["additional_co2"] >= 0.0
    assert bid["capacity_remaining"] == 180.0


def test_multiple_bids_selection_minimum_detour():
    road, order, node_coords, node_id_map = setup_bidding_scenario()

    # Broken truck carrying ORD_100
    t_broken = Vehicle(vehicle_id="T_BROKEN", max_weight=200.0, assigned_orders=["ORD_100"])
    # T_NEAR: closer route (small detour)
    t_near = Vehicle(vehicle_id="T_NEAR", max_weight=200.0, current_route=[0, 1, 0])
    # T_FAR: far route (larger detour)
    t_far = Vehicle(vehicle_id="T_FAR", max_weight=200.0, current_route=[0, 3, 0])

    fleet = FleetState(
        vehicles={"T_BROKEN": t_broken, "T_NEAR": t_near, "T_FAR": t_far},
        active_orders={"ORD_100": order},
    )
    mesh = MeshNetwork(transmission_range_km=100.0, seed=42)
    fleet_agent = FleetAgent(fleet_state=fleet, road_network=road, mesh_network=mesh, seed=42)

    res = fleet_agent.on_vehicle_breakdown_decentralized("T_BROKEN", current_time_mins=10.0, node_id_map=node_id_map)
    assert res["success"] is True
    assert res["recovered_count"] == 1
    # Winner must be T_NEAR due to lower detour
    winner_veh = res["transfers"][0]["to_vehicle"]
    assert winner_veh == "T_NEAR"


def test_deterministic_tie_break():
    road, order, node_coords, node_id_map = setup_bidding_scenario()

    t_broken = Vehicle(vehicle_id="T_BROKEN", max_weight=200.0, assigned_orders=["ORD_100"])
    # Two identical vehicles with identical coordinates & routes
    t_beta = Vehicle(vehicle_id="T_BETA", max_weight=200.0, current_route=[0, 2, 0])
    t_alpha = Vehicle(vehicle_id="T_ALPHA", max_weight=200.0, current_route=[0, 2, 0])

    fleet = FleetState(
        vehicles={"T_BROKEN": t_broken, "T_BETA": t_beta, "T_ALPHA": t_alpha},
        active_orders={"ORD_100": order},
    )
    mesh = MeshNetwork(transmission_range_km=100.0, seed=42)
    fleet_agent = FleetAgent(fleet_state=fleet, road_network=road, mesh_network=mesh, seed=42)

    res = fleet_agent.on_vehicle_breakdown_decentralized("T_BROKEN", current_time_mins=10.0, node_id_map=node_id_map)
    assert res["success"] is True
    # Deterministic tie-break must pick lexicographically lower T_ALPHA
    assert res["transfers"][0]["to_vehicle"] == "T_ALPHA"


def test_invalid_bid_rejection():
    road, order, node_coords, node_id_map = setup_bidding_scenario()

    t_broken = Vehicle(vehicle_id="T_BROKEN", max_weight=200.0, assigned_orders=["ORD_100"])
    fleet = FleetState(
        vehicles={"T_BROKEN": t_broken},
        active_orders={"ORD_100": order},
    )
    mesh = MeshNetwork(transmission_range_km=100.0, seed=42)
    fleet_agent = FleetAgent(fleet_state=fleet, road_network=road, mesh_network=mesh, seed=42)

    # Empty fleet cannot absorb order
    res = fleet_agent.on_vehicle_breakdown_decentralized("T_BROKEN", current_time_mins=10.0, node_id_map=node_id_map)
    assert res["success"] is False
    assert res["recovered_count"] == 0
    assert res["unrecovered_count"] == 1


def test_no_feasible_bidder_due_to_capacity():
    road, order, node_coords, node_id_map = setup_bidding_scenario()

    t_broken = Vehicle(vehicle_id="T_BROKEN", max_weight=200.0, assigned_orders=["ORD_100"])
    # T_FULL has no remaining capacity (max 200, current load 195, order requires 20)
    t_full = Vehicle(vehicle_id="T_FULL", max_weight=200.0, current_load=195.0, current_route=[0, 2, 0])

    fleet = FleetState(
        vehicles={"T_BROKEN": t_broken, "T_FULL": t_full},
        active_orders={"ORD_100": order},
    )
    mesh = MeshNetwork(transmission_range_km=100.0, seed=42)
    fleet_agent = FleetAgent(fleet_state=fleet, road_network=road, mesh_network=mesh, seed=42)

    res = fleet_agent.on_vehicle_breakdown_decentralized("T_BROKEN", current_time_mins=10.0, node_id_map=node_id_map)
    assert res["success"] is False
    assert res["recovered_count"] == 0
    assert res["unrecovered_count"] == 1


def test_winner_receiving_reassigned_order_and_updating_route():
    road, order, node_coords, node_id_map = setup_bidding_scenario()

    t_broken = Vehicle(vehicle_id="T_BROKEN", max_weight=200.0, assigned_orders=["ORD_100"])
    t_helper = Vehicle(vehicle_id="T_HELPER", max_weight=200.0, current_route=[0, 2, 0])

    fleet = FleetState(
        vehicles={"T_BROKEN": t_broken, "T_HELPER": t_helper},
        active_orders={"ORD_100": order},
    )
    mesh = MeshNetwork(transmission_range_km=100.0, seed=42)
    fleet_agent = FleetAgent(fleet_state=fleet, road_network=road, mesh_network=mesh, seed=42)

    res = fleet_agent.on_vehicle_breakdown_decentralized("T_BROKEN", current_time_mins=10.0, node_id_map=node_id_map)
    assert res["success"] is True

    helper_agent = fleet_agent.truck_agents["T_HELPER"]
    # Helper agent must now have the order in assigned_orders and route
    assert "ORD_100" in helper_agent.state.assigned_orders
    assert 1 in helper_agent.state.current_route
    assert helper_agent.state.current_load == 20.0
    assert "ORD_100" in helper_agent.state.accepted_transfers
