import pytest
from src.models.order import Order, OrderStatus
from src.models.vehicle import Vehicle, VehicleStatus
from src.models.road import RoadNetwork
from src.models.fleet_state import FleetState, ConnectivityState
from src.networking.mesh import MeshNetwork
from src.networking.messages import MeshMessage, MessageType
from src.agents.truck_agent import TruckAgent, LocalAgentState
from src.agents.fleet_agent import FleetAgent
from src.agents.centralized_agent import CentralizedAgent


def test_truck_agent_local_state_isolation():
    veh = Vehicle(vehicle_id="T1", max_weight=200.0, current_route=[0, 1, 0])
    agent = TruckAgent(vehicle_id="T1", initial_vehicle=veh)

    # Verify agent operates on isolated LocalAgentState
    assert isinstance(agent.state, LocalAgentState)
    assert agent.state.vehicle_id == "T1"
    assert agent.state.max_weight == 200.0
    assert agent.remaining_capacity() == 200.0


def test_truck_agent_bid_acceptance_and_rejection():
    veh = Vehicle(vehicle_id="T2", max_weight=100.0, current_route=[0, 1, 0])
    agent = TruckAgent(vehicle_id="T2", initial_vehicle=veh)
    agent.state.current_load = 80.0  # Only 20 kg remaining capacity

    node_coords = {0: (0.0, 0.0), 1: (10.0, 0.0), 2: (5.0, 5.0), 3: (50.0, 50.0)}

    # Order A: 15 kg (feasible)
    ord_a = Order(
        order_id="ORD_A",
        pickup_location=(0.0, 0.0),
        destination=(5.0, 5.0),
        demand_weight=15.0,
        latest_delivery=60.0,
    )
    feasible_a, detour_a, idx_a = agent.evaluate_order_absorption(ord_a, 2, node_coords)
    assert feasible_a is True
    assert detour_a > 0.0
    assert idx_a == 1

    # Order B: 30 kg (exceeds capacity: 80 + 30 > 100)
    ord_b = Order(
        order_id="ORD_B",
        pickup_location=(0.0, 0.0),
        destination=(5.0, 5.0),
        demand_weight=30.0,
        latest_delivery=60.0,
    )
    feasible_b, detour_b, idx_b = agent.evaluate_order_absorption(ord_b, 2, node_coords)
    assert feasible_b is False


def test_fleet_agent_decentralized_mesh_recovery():
    road = RoadNetwork()
    road.add_node(0, x=0.0, y=0.0)
    road.add_node(1, x=10.0, y=0.0)
    road.add_node(2, x=20.0, y=0.0)

    ord1 = Order(order_id="O1", destination=(10.0, 0.0), demand_weight=30.0, latest_delivery=60.0)
    ord2 = Order(order_id="O2", destination=(20.0, 0.0), demand_weight=40.0, latest_delivery=90.0)

    # T1 carries O1 and O2
    t1 = Vehicle(vehicle_id="T1", max_weight=200.0, current_route=[0, 1, 2, 0], assigned_orders=["O1", "O2"])
    # T2 has spare capacity (empty)
    t2 = Vehicle(vehicle_id="T2", max_weight=200.0, current_route=[0, 0], assigned_orders=[])

    fleet = FleetState(
        vehicles={"T1": t1, "T2": t2},
        active_orders={"O1": ord1, "O2": ord2},
        road_network=road,
    )
    node_map = {"O1": 1, "O2": 2}
    mesh = MeshNetwork(transmission_range_km=50.0, packet_loss_per_hop=0.0, seed=42)

    fleet_agent = FleetAgent(fleet_state=fleet, road_network=road, mesh_network=mesh, seed=42)

    # T1 breaks down
    res = fleet_agent.on_vehicle_breakdown_decentralized("T1", current_time_mins=10.0, node_id_map=node_map)
    assert res["success"] is True
    assert res["recovered_count"] > 0
    assert res["mesh_messages"] > 0
    assert "T2" in [t["to_vehicle"] for t in res["transfers"]]


def test_state_synchronization_on_reconnect():
    road = RoadNetwork()
    t1 = Vehicle(vehicle_id="T1", max_weight=200.0)
    t2 = Vehicle(vehicle_id="T2", max_weight=200.0)
    fleet = FleetState(vehicles={"T1": t1, "T2": t2}, connectivity_state=ConnectivityState.MESH_MODE)

    fleet_agent = FleetAgent(fleet_state=fleet, road_network=road)

    # Simulate conflict during offline operation: both T1 and T2 claim order "O_SHARED"
    fleet_agent.truck_agents["T1"].state.assigned_orders = ["O_SHARED"]
    fleet_agent.truck_agents["T2"].state.assigned_orders = ["O_SHARED"]

    sync_res = fleet_agent.synchronize_state_on_reconnect()
    assert sync_res["status"] == "SYNCHRONIZED"
    assert sync_res["conflicts_resolved"] == 1
    # Canonical rule: lexicographical tie break selects T1
    assert sync_res["authoritative_assignments"]["O_SHARED"] == "T1"
    assert "O_SHARED" in fleet.vehicles["T1"].assigned_orders
    assert "O_SHARED" not in fleet.vehicles["T2"].assigned_orders
    assert fleet.connectivity_state == ConnectivityState.CLOUD_MODE
