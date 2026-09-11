import pytest
import numpy as np
from src.rl.environment import (
    SWARMRLEnv,
    ACTION_ASSIGN_BEST_ORDER,
    ACTION_REASSIGN_STRANDED_ORDER,
    ACTION_ACCEPT_OR_REJECT_TRANSFER,
    ACTION_REPOSITION_TO_DEMAND_ZONE,
    ACTION_HOLD_OR_CONTINUE,
)
from src.models.order import Order, OrderStatus
from src.models.vehicle import Vehicle, VehicleStatus
from src.models.road import RoadNetwork
from src.models.fleet_state import FleetState, ConnectivityState
from src.agents.truck_agent import TruckAgent
from src.agents.fleet_agent import FleetAgent
from src.networking.mesh import MeshNetwork
from src.networking.messages import MeshMessage, MessageType
from src.evaluation.metrics import (
    calculate_average_delivery_delay,
    calculate_completion_rate,
)
from src.optimization.vrptw import VRPTWSolver
from src.optimization.route_optimizer import RouteOptimizer
from src.prediction.travel_time import TravelTimePredictor
from src.prediction.fuel_ml import FuelConsumptionPredictor
from src.data.loaders.solomon import load_solomon_benchmark


def test_ppo_action_changes_simulation_decision():
    """Verify that different PPO actions produce distinct decisions and trajectory outcomes."""
    env1 = SWARMRLEnv(dataset_name="C101", num_customers=15, num_vehicles=3, seed=42)
    env1.reset(seed=42)
    # Break down vehicle 1 in both environments
    v1_broken = env1.env.fleet_state.vehicles[list(env1.env.fleet_state.vehicles.keys())[1]]
    v1_broken.status = VehicleStatus.BROKEN_DOWN
    
    env2 = SWARMRLEnv(dataset_name="C101", num_customers=15, num_vehicles=3, seed=42)
    env2.reset(seed=42)
    v2_broken = env2.env.fleet_state.vehicles[list(env2.env.fleet_state.vehicles.keys())[1]]
    v2_broken.status = VehicleStatus.BROKEN_DOWN
    
    # Env 1 takes REASSIGN_STRANDED_ORDER, Env 2 takes HOLD_OR_CONTINUE
    next_obs1, r1, _, _, info1 = env1.step(ACTION_REASSIGN_STRANDED_ORDER)
    next_obs2, r2, _, _, info2 = env2.step(ACTION_HOLD_OR_CONTINUE)
    
    # Decisions, observations, and rewards must diverge
    assert not np.array_equal(next_obs1, next_obs2)
    assert r1 != r2
    assert info1 != info2


def test_rule_based_recovery_does_not_execute_before_ppo():
    """Verify that stranded orders from breakdowns are not automatically resolved by FleetAgent before PPO gets to decide."""
    env = SWARMRLEnv(dataset_name="C101", num_customers=15, num_vehicles=3, seed=42)
    env.reset(seed=42)
    
    # Break down vehicle 1
    vehicles = list(env.env.fleet_state.vehicles.values())
    broken_veh = vehicles[1]
    broken_veh.status = VehicleStatus.BROKEN_DOWN
    assert len(broken_veh.assigned_orders) > 0
    stranded_id = broken_veh.assigned_orders[0]
    
    # Step with HOLD_OR_CONTINUE: order should NOT be magically recovered by an implicit background agent
    env.step(ACTION_HOLD_OR_CONTINUE)
    assert stranded_id in broken_veh.assigned_orders


def test_ppo_can_recover_stranded_order():
    """Verify that taking ACTION_REASSIGN_STRANDED_ORDER allows PPO to recover stranded cargo."""
    env = SWARMRLEnv(dataset_name="C101", num_customers=15, num_vehicles=3, seed=42)
    env.reset(seed=42)
    
    # Mark vehicle 1 broken down with orders
    vehicles = list(env.env.fleet_state.vehicles.values())
    broken_veh = vehicles[1]
    broken_veh.status = VehicleStatus.BROKEN_DOWN
    assert len(broken_veh.assigned_orders) > 0
    stranded_id = broken_veh.assigned_orders[0]
    orig_load = broken_veh.current_load
    
    # Target recipient vehicle 0 has remaining capacity
    ctrl_veh = env.env.fleet_state.vehicles[env.controlled_truck_id]
    ctrl_veh.current_load = 0.0
    
    # Identical baseline env that holds instead of recovering
    env_baseline = SWARMRLEnv(dataset_name="C101", num_customers=15, num_vehicles=3, seed=42)
    env_baseline.reset(seed=42)
    broken_b = env_baseline.env.fleet_state.vehicles[broken_veh.vehicle_id]
    broken_b.status = VehicleStatus.BROKEN_DOWN
    _, reward_hold, _, _, _ = env_baseline.step(ACTION_HOLD_OR_CONTINUE)
    
    # Take PPO action 1: REASSIGN_STRANDED_ORDER
    next_obs, reward, terminated, truncated, info = env.step(ACTION_REASSIGN_STRANDED_ORDER)
    
    # Stranded order must now be transferred from broken vehicle
    assert stranded_id not in broken_veh.assigned_orders
    assert broken_veh.current_load < orig_load or broken_veh.current_load == 0.0
    assert reward > reward_hold  # Recovery reward strictly beats passive holding


def test_ppo_can_reject_infeasible_transfer():
    """Verify that accepting an infeasible transfer (exceeding truck capacity) is rejected."""
    env = SWARMRLEnv(dataset_name="C101", num_customers=15, num_vehicles=3, seed=42)
    env.reset(seed=42)
    
    ctrl_veh = env.env.fleet_state.vehicles[env.controlled_truck_id]
    ctrl_veh.current_load = ctrl_veh.max_weight  # Full capacity
    
    # Mark an order as REASSIGNED
    reassigned_ord = next(iter(env.env.fleet_state.active_orders.values()))
    reassigned_ord.status = OrderStatus.REASSIGNED
    
    # Action 2: ACCEPT_OR_REJECT_TRANSFER
    next_obs, reward, terminated, truncated, info = env.step(ACTION_ACCEPT_OR_REJECT_TRANSFER)
    
    # Capacity must not be exceeded
    assert ctrl_veh.current_load <= ctrl_veh.max_weight


def test_ppo_can_reposition_truck():
    """Verify that ACTION_REPOSITION_TO_DEMAND_ZONE alters the idle truck route towards a high demand centroid."""
    env = SWARMRLEnv(dataset_name="C101", num_customers=15, num_vehicles=3, seed=42)
    env.reset(seed=42)
    
    ctrl_veh = env.env.fleet_state.vehicles[env.controlled_truck_id]
    ctrl_veh.status = VehicleStatus.IDLE
    ctrl_veh.current_route = [0, 0]
    
    # Execute action 3: REPOSITION
    env.step(ACTION_REPOSITION_TO_DEMAND_ZONE)
    
    # Truck route or status is updated to repositioning
    assert ctrl_veh.status == VehicleStatus.EN_ROUTE or len(ctrl_veh.current_route) > 1


def test_ml_prediction_changes_routing_objective():
    """Verify that travel time and fuel ML predictions change the VRPTW solution compared to static physics."""
    fleet, network, meta = load_solomon_benchmark("C101", max_customers=15, vehicle_count=3)
    depot = meta["depot_coord"]
    vehicles = list(fleet.vehicles.values())
    cust_orders = list(fleet.active_orders.values())
    
    # 1. Static Physics Solver
    solver = VRPTWSolver()
    res_static = solver.solve(
        vehicles=vehicles,
        orders=cust_orders,
        road_network=network,
        time_limit_sec=5,
    )
    
    # 2. ML-Informed Solver with trained models
    tt_model = TravelTimePredictor(random_state=42)
    X_tt, y_tt = TravelTimePredictor.generate_synthetic_trip_data(num_samples=200, seed=42)
    tt_model.train(X_tt, y_tt)
    
    fuel_model = FuelConsumptionPredictor(random_state=42)
    X_fuel, y_fuel = FuelConsumptionPredictor.generate_synthetic_fuel_data(num_samples=200, seed=42)
    fuel_model.train(X_fuel, y_fuel)
    
    res_ml = solver.solve(
        vehicles=vehicles,
        orders=cust_orders,
        road_network=network,
        time_limit_sec=5,
        travel_time_predictor=tt_model,
        fuel_predictor=fuel_model,
    )
    
    # Objectives or solved costs must reflect ML edge predictions
    assert res_ml.total_objective_cost != res_static.total_objective_cost or res_ml.routes != res_static.routes


def test_mesh_unreachable_truck_cannot_bid():
    """Verify that a partitioned / unreachable truck cannot bid or win order transfers."""
    road = RoadNetwork()
    road.add_node(0, x=0.0, y=0.0)
    road.add_node(1, x=5.0, y=0.0)
    road.add_node(2, x=100.0, y=0.0)
    
    ord0 = Order(order_id="ORD0", destination=(5.0, 0.0), demand_weight=10.0, latest_delivery=100.0)
    
    t0 = Vehicle(vehicle_id="T0", max_weight=50.0, current_location=(0.0, 0.0), current_route=[0, 1, 0], assigned_orders=["ORD0"], current_load=10.0, status=VehicleStatus.BROKEN_DOWN)
    t1 = Vehicle(vehicle_id="T1", max_weight=50.0, current_location=(5.0, 0.0), current_route=[0, 0], assigned_orders=[], current_load=0.0)
    t2 = Vehicle(vehicle_id="T2", max_weight=50.0, current_location=(100.0, 0.0), current_route=[0, 0], assigned_orders=[], current_load=0.0)
    
    fleet = FleetState(
        vehicles={"T0": t0, "T1": t1, "T2": t2},
        active_orders={"ORD0": ord0},
        road_network=road,
    )
    mesh = MeshNetwork(transmission_range_km=10.0, packet_loss_per_hop=0.0, seed=42)
    fleet_agent = FleetAgent(fleet_state=fleet, road_network=road, mesh_network=mesh, seed=42)
    
    node_map = {"ORD0": 1}
    res = fleet_agent.on_vehicle_breakdown_decentralized("T0", current_time_mins=10.0, node_id_map=node_map)
    
    # Must recover to reachable T1, never to unreachable T2
    assert res["success"] is True
    assert len(res["transfers"]) == 1
    assert res["transfers"][0]["to_vehicle"] == "T1"
    assert res["transfers"][0]["to_vehicle"] != "T2"


def test_duplicate_order_transfer_is_impossible():
    """Verify that an order cannot be simultaneously reassigned to multiple vehicles."""
    road = RoadNetwork()
    road.add_node(0, x=0.0, y=0.0)
    road.add_node(1, x=5.0, y=0.0)
    
    ord_dup = Order(order_id="ORD_DUP", destination=(5.0, 0.0), demand_weight=10.0, latest_delivery=100.0)
    t_a = Vehicle(vehicle_id="TA", max_weight=50.0, current_location=(0.0, 0.0), current_route=[0, 1, 0], assigned_orders=["ORD_DUP"], current_load=10.0, status=VehicleStatus.BROKEN_DOWN)
    t_b = Vehicle(vehicle_id="TB", max_weight=50.0, current_location=(2.0, 0.0), current_route=[0, 0], assigned_orders=[], current_load=0.0)
    
    fleet = FleetState(
        vehicles={"TA": t_a, "TB": t_b},
        active_orders={"ORD_DUP": ord_dup},
        road_network=road,
    )
    mesh = MeshNetwork(transmission_range_km=15.0, packet_loss_per_hop=0.0, seed=42)
    fleet_agent = FleetAgent(fleet_state=fleet, road_network=road, mesh_network=mesh, seed=42)
    node_map = {"ORD_DUP": 1}
    
    res = fleet_agent.on_vehicle_breakdown_decentralized("TA", current_time_mins=5.0, node_id_map=node_map)
    assert res["success"] is True
    
    # Check edge agent states
    assert "ORD_DUP" in fleet_agent.truck_agents["TB"].state.assigned_orders
    assert "ORD_DUP" not in fleet_agent.truck_agents["TA"].state.assigned_orders
    
    # Synchronize state on reconnect
    fleet_agent.synchronize_state_on_reconnect()
    assert "ORD_DUP" in fleet.vehicles["TB"].assigned_orders
    assert "ORD_DUP" not in fleet.vehicles["TA"].assigned_orders
    
    # Verify no duplicate assignments anywhere in fleet
    total_occ = sum(1 for v in fleet.vehicles.values() if "ORD_DUP" in v.assigned_orders)
    assert total_occ == 1


def test_metrics_definition_and_denominator_fix():
    """Verify that calculate_average_delivery_delay correctly normalizes by delayed orders without denominator distortion."""
    # 2 delayed orders, 1 on-time order, 1 failed/unfulfilled order
    orders = [
        Order(order_id="O1", destination=(0,0), demand_weight=1, latest_delivery=20, actual_delivery_time=30.0, status=OrderStatus.DELIVERED), # delay = 10
        Order(order_id="O2", destination=(0,0), demand_weight=1, latest_delivery=20, actual_delivery_time=40.0, status=OrderStatus.DELIVERED), # delay = 20
        Order(order_id="O3", destination=(0,0), demand_weight=1, latest_delivery=50, actual_delivery_time=45.0, status=OrderStatus.DELIVERED), # on-time
        Order(order_id="O4", destination=(0,0), demand_weight=1, latest_delivery=50, actual_delivery_time=None, status=OrderStatus.FAILED),    # failed
    ]
    
    avg_delay = calculate_average_delivery_delay(orders)
    # Total delay = 10 + 20 = 30. Denominator = 2 delayed orders. Avg = 15.0
    assert avg_delay == pytest.approx(15.0, abs=1e-3)
    
    # Verify metric consistency: completed + failed == total
    delivered = sum(1 for o in orders if o.status == OrderStatus.DELIVERED)
    failed = sum(1 for o in orders if o.status == OrderStatus.FAILED)
    assert delivered == 3
    assert failed == 1
    assert delivered + failed == len(orders)
    assert calculate_completion_rate(len(orders), delivered) == 75.0


def test_seed_reproducibility():
    """Verify that identical seeds yield identical initial states and trajectories, while different seeds produce different stochastic sequences."""
    env_a = SWARMRLEnv(dataset_name="C101", num_customers=15, num_vehicles=3, seed=42)
    obs_a1, _ = env_a.reset(seed=42)
    obs_a2, r_a, _, _, _ = env_a.step(ACTION_HOLD_OR_CONTINUE)
    
    env_b = SWARMRLEnv(dataset_name="C101", num_customers=15, num_vehicles=3, seed=42)
    obs_b1, _ = env_b.reset(seed=42)
    obs_b2, r_b, _, _, _ = env_b.step(ACTION_HOLD_OR_CONTINUE)
    
    np.testing.assert_array_equal(obs_a1, obs_b1)
    np.testing.assert_array_equal(obs_a2, obs_b2)
    assert r_a == r_b
    
    # Verify stochastic network outcome is reproducible for identical seeds and diverges for different seeds
    mesh_1 = MeshNetwork(transmission_range_km=15.0, packet_loss_per_hop=0.5, seed=42)
    mesh_2 = MeshNetwork(transmission_range_km=15.0, packet_loss_per_hop=0.5, seed=42)
    mesh_3 = MeshNetwork(transmission_range_km=15.0, packet_loss_per_hop=0.5, seed=999)
    
    seq1 = [mesh_1.rng.random() for _ in range(10)]
    seq2 = [mesh_2.rng.random() for _ in range(10)]
    seq3 = [mesh_3.rng.random() for _ in range(10)]
    
    assert seq1 == seq2
    assert seq1 != seq3


def test_reward_decomposition_explainability():
    """Verify that calculate_step_reward_decomposed returns consistent scalar and explainable dict."""
    from src.rl.reward import calculate_step_reward_decomposed
    
    total, decomp = calculate_step_reward_decomposed(
        new_deliveries=2,
        new_on_time=2,
        new_recoveries=1,
        new_failed=0,
        new_late=0,
        delay_minutes=5.0,
        incremental_distance_km=12.0,
        incremental_fuel_liters=3.5,
        incremental_co2_kg=9.2,
        incremental_empty_km=1.5,
        useful_repositioning=True,
    )
    
    # Check that all expected keys exist
    expected_keys = [
        "delivery_reward", "ontime_reward", "recovery_reward",
        "fuel_penalty", "distance_penalty", "delay_penalty", "failure_penalty", "total_reward"
    ]
    for k in expected_keys:
        assert k in decomp
    
    assert total == decomp["total_reward"]
    assert decomp["delivery_reward"] > 0.0
    assert decomp["fuel_penalty"] > 0.0
    assert decomp["recovery_reward"] > 0.0


def test_scenario_generator_determinism_and_variance():
    """Verify that scenario generator is deterministic per seed, and produces real variance across different seeds."""
    from src.evaluation.scenario_generator import generate_benchmark_scenario
    
    scen_42_a = generate_benchmark_scenario(seed=42, dataset_name="C101", customers_count=20, vehicles_count=5)
    scen_42_b = generate_benchmark_scenario(seed=42, dataset_name="C101", customers_count=20, vehicles_count=5)
    scen_99 = generate_benchmark_scenario(seed=99, dataset_name="C101", customers_count=20, vehicles_count=5)
    
    brk_a = scen_42_a.get_breakdown_spec()
    brk_b = scen_42_b.get_breakdown_spec()
    brk_99 = scen_99.get_breakdown_spec()
    
    # Identical seeds must match exactly
    assert brk_a.timestamp_mins == brk_b.timestamp_mins
    assert brk_a.payload["vehicle_id"] == brk_b.payload["vehicle_id"]
    
    # Different seeds must produce variation in timing or vehicle
    assert (brk_a.timestamp_mins != brk_99.timestamp_mins) or (brk_a.payload["vehicle_id"] != brk_99.payload["vehicle_id"])


def test_observation_vector_bounded_and_leak_free():
    """Verify that observation vector matches OBS_DIM, is finite, and strictly bounded with no NaN/Inf."""
    env = SWARMRLEnv(dataset_name="C101", num_customers=15, num_vehicles=3, seed=42)
    obs, info = env.reset(seed=42)
    
    assert obs.shape == (env.OBS_DIM,)
    assert not np.isnan(obs).any()
    assert not np.isinf(obs).any()
    
    # Check normalized bounds
    assert np.all(obs >= -1.5)
    assert np.all(obs <= 2.5)
    
    # Observation must dynamically change when state changes
    v = env.env.fleet_state.vehicles[list(env.env.fleet_state.vehicles.keys())[0]]
    v.status = VehicleStatus.BROKEN_DOWN
    obs_after = env._get_observation()
    assert not np.array_equal(obs, obs_after)


def test_calculate_recovery_rate_and_communication_overhead():
    """Verify recovery rate and communication overhead calculations."""
    from src.evaluation.metrics import calculate_recovery_rate, calculate_communication_overhead
    
    # Recovery rate
    rate = calculate_recovery_rate(recovered_orders=3, stranded_orders=4)
    assert rate == 75.0
    
    rate_zero = calculate_recovery_rate(recovered_orders=0, stranded_orders=0)
    assert rate_zero == 100.0  # No stranded orders means 100% operational intactness
    
    # Communication overhead
    mesh = MeshNetwork(transmission_range_km=25.0, seed=42)
    mesh.total_packets_transmitted = 18
    mesh.total_bytes_transmitted = 2340
    comm = calculate_communication_overhead(mesh)
    assert comm["messages_exchanged"] == 18
    assert comm["bytes_transmitted"] == 2340


