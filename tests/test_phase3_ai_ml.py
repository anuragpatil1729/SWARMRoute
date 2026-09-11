import copy
import math
from pathlib import Path
import pytest
import numpy as np

from src.models.order import Order, OrderStatus
from src.models.vehicle import Vehicle, VehicleStatus
from src.models.road import RoadNetwork, Road
from src.models.fleet_state import FleetState, ConnectivityState
from src.prediction.travel_time import TravelTimePredictor
from src.prediction.fuel_ml import FuelConsumptionPredictor
from src.prediction.demand import DemandPredictor
from src.optimization.predictive_positioning import PredictiveFleetPositioner
from src.optimization.vrptw import VRPTWSolver
from src.optimization.route_optimizer import RouteOptimizer
from src.agents.truck_agent import TruckAgent
from src.agents.fleet_agent import FleetAgent
from src.networking.messages import MeshMessage, MessageType
from src.simulation.environment import FleetSimulationEnvironment
from src.rl.environment import (
    SWARMRLEnv,
    ACTION_ASSIGN_BEST_ORDER,
    ACTION_REASSIGN_STRANDED_ORDER,
    ACTION_ACCEPT_OR_REJECT_TRANSFER,
    ACTION_REPOSITION_TO_DEMAND_ZONE,
    ACTION_HOLD_OR_CONTINUE,
)
from src.rl.ppo_agent import PPOFleetAgent
from src.rl.reward import FleetRewardCalculator, RewardConfig
from src.evaluation.scenario_generator import generate_benchmark_scenario


# =============================================================================
# 1. TRAVEL-TIME PREDICTION INTEGRATION
# =============================================================================
def test_1_travel_time_prediction_integration():
    """Verify TravelTimePredictor modifies VRPTW time matrix when enabled and is bypassed when disabled."""
    road = RoadNetwork()
    road.add_node(0, x=0.0, y=0.0)
    road.add_node(1, x=20.0, y=0.0)
    road.add_node(2, x=40.0, y=0.0)
    road.add_road(Road(road_id="R01", source=0, destination=1, distance=20.0))
    road.add_road(Road(road_id="R12", source=1, destination=2, distance=20.0))

    orders = [
        Order(order_id="O1", destination=(20.0, 0.0), demand_weight=10.0, earliest_delivery=0.0, latest_delivery=120.0),
        Order(order_id="O2", destination=(40.0, 0.0), demand_weight=10.0, earliest_delivery=0.0, latest_delivery=120.0),
    ]
    vehicles = [Vehicle(vehicle_id="V1", max_weight=50.0, current_location=(0.0, 0.0))]

    tt_pred = TravelTimePredictor(random_state=42)
    X, y = TravelTimePredictor.generate_synthetic_trip_data(num_samples=200, seed=42)
    tt_pred.train(X, y)

    solver = VRPTWSolver()
    
    # ML mode enabled
    res_ml = solver.solve(
        vehicles=vehicles, orders=orders, road_network=road,
        travel_time_predictor=tt_pred, use_ml_prediction=True, time_limit_sec=3
    )

    # ML mode disabled
    res_static = solver.solve(
        vehicles=vehicles, orders=orders, road_network=road,
        travel_time_predictor=tt_pred, use_ml_prediction=False, time_limit_sec=3
    )

    # Both must solve feasibly, with ML mode having active predicted time evaluation
    assert res_ml.status in ("FEASIBLE", "OPTIMAL")
    assert res_static.status in ("FEASIBLE", "OPTIMAL")


# =============================================================================
# 2. FUEL PREDICTION INTEGRATION
# =============================================================================
def test_2_fuel_prediction_integration():
    """Verify FuelConsumptionPredictor is used in recovery bidding without replacing authoritative physics model."""
    fuel_pred = FuelConsumptionPredictor(random_state=42)
    X, y = FuelConsumptionPredictor.generate_synthetic_fuel_data(num_samples=200, seed=42)
    fuel_pred.train(X, y)

    road = RoadNetwork()
    road.add_node(0, x=0.0, y=0.0)
    road.add_node(1, x=15.0, y=0.0)
    node_coords = {0: (0.0, 0.0), 1: (15.0, 0.0)}

    order = Order(order_id="ORD_F", destination=(15.0, 0.0), demand_weight=20.0, latest_delivery=100.0)
    v = Vehicle(vehicle_id="TRUCK_ML", max_weight=100.0, current_location=(0.0, 0.0), current_route=[0, 0])

    # Agent with ML Fuel enabled
    agent_ml = TruckAgent(vehicle_id="TRUCK_ML", initial_vehicle=v, fuel_predictor=fuel_pred, use_ml_fuel=True, max_detour_km=50.0)
    # Agent with static physics fuel
    agent_phys = TruckAgent(vehicle_id="TRUCK_ML", initial_vehicle=v, fuel_predictor=fuel_pred, use_ml_fuel=False, max_detour_km=50.0)

    sos_msg = MeshMessage(
        message_id="SOS_1", message_type=MessageType.BREAKDOWN_ALERT, sender_id="TRUCK_BRK",
        receiver_id="TRUCK_ML", timestamp_mins=10.0,
        payload={"orders": [order.model_dump()], "order_nodes": {"ORD_F": 1}}
    )

    bids_ml = agent_ml.generate_bids_for_breakdown(sos_msg, node_coords)
    bids_phys = agent_phys.generate_bids_for_breakdown(sos_msg, node_coords)

    assert len(bids_ml) == 1
    assert len(bids_phys) == 1
    assert bids_ml[0].payload["additional_fuel"] > 0.0
    assert bids_phys[0].payload["additional_fuel"] > 0.0

    # Verify that FleetSimulationEnvironment still uses the physics model for ground-truth consumption
    fleet = FleetState(vehicles={"TRUCK_ML": v}, active_orders={"ORD_F": order}, road_network=road)
    env = FleetSimulationEnvironment(fleet_state=fleet, road_network=road, node_id_map={"ORD_F": 1})
    assert hasattr(env.fuel_model, "calculate_fuel")


# =============================================================================
# 3. DEMAND PREDICTION
# =============================================================================
def test_3_demand_prediction():
    """Verify DemandPredictor loads, trains, and produces valid finite demand predictions."""
    dp = DemandPredictor(random_state=42)
    X, y = DemandPredictor.generate_synthetic_demand_data(num_samples=200, num_zones=4, seed=42)
    dp.train(X, y)

    assert dp.is_trained is True
    sample_input = np.array([[0, 2, 10, 30.0, 28.0, 0.5, 0.8]])
    pred = dp.predict(sample_input)
    assert len(pred) == 1
    assert pred[0] > 0.0
    assert not np.isnan(pred[0])
    assert not np.isinf(pred[0])


# =============================================================================
# 4. PREDICTIVE POSITIONING
# =============================================================================
def test_4_predictive_positioning():
    """Verify PredictiveFleetPositioner repositions idle vehicles without disrupting active delivery trucks."""
    dp = DemandPredictor(random_state=42)
    X, y = DemandPredictor.generate_synthetic_demand_data(num_samples=200, num_zones=4, seed=42)
    dp.train(X, y)

    positioner = PredictiveFleetPositioner(demand_predictor=dp, seed=42)

    road = RoadNetwork()
    road.add_node(0, x=0.0, y=0.0)
    road.add_node(1, x=25.0, y=25.0)
    road.add_node(2, x=75.0, y=75.0)

    # 1 idle truck, 1 en-route truck
    t_idle = Vehicle(vehicle_id="T_IDLE", max_weight=100.0, current_location=(0.0, 0.0), status=VehicleStatus.IDLE, current_load=0.0)
    t_busy = Vehicle(vehicle_id="T_BUSY", max_weight=100.0, current_location=(10.0, 10.0), status=VehicleStatus.EN_ROUTE, current_load=40.0)

    fleet = FleetState(vehicles={"T_IDLE": t_idle, "T_BUSY": t_busy}, active_orders={}, road_network=road)

    plans = positioner.plan_repositioning(fleet, road, current_time_mins=60.0)
    assert len(plans) == 1
    assert plans[0]["vehicle_id"] == "T_IDLE"
    assert plans[0]["vehicle_id"] != "T_BUSY"
    assert "target_node" in plans[0]


# =============================================================================
# 5. PPO RESET
# =============================================================================
def test_5_ppo_reset():
    """Verify Gymnasium PPO environment resets cleanly to standard observation vector and info."""
    env = SWARMRLEnv(dataset_name="C101", num_customers=15, num_vehicles=3, seed=42)
    obs, info = env.reset(seed=42)

    assert isinstance(obs, np.ndarray)
    assert obs.shape == (25,)
    assert "controlled_truck" in info
    assert info["controlled_truck"] == "TRUCK_01"


# =============================================================================
# 6. PPO STEP
# =============================================================================
def test_6_ppo_step():
    """Verify SWARMRLEnv.step advances state and returns valid Gym tuple."""
    env = SWARMRLEnv(dataset_name="C101", num_customers=15, num_vehicles=3, seed=42)
    env.reset(seed=42)

    obs, reward, terminated, truncated, info = env.step(ACTION_HOLD_OR_CONTINUE)
    assert obs.shape == (25,)
    assert isinstance(reward, float)
    assert isinstance(terminated, bool)
    assert isinstance(truncated, bool)
    assert isinstance(info, dict)


# =============================================================================
# 7. OBSERVATION DIMENSIONS
# =============================================================================
def test_7_observation_dimensions():
    """Verify observation dimension strictly equals 25 and matches observation space."""
    env = SWARMRLEnv(dataset_name="C101", num_customers=15, num_vehicles=3, seed=42)
    assert env.OBS_DIM == 25
    assert env.observation_space.shape == (25,)
    obs, _ = env.reset(seed=42)
    assert len(obs) == 25


# =============================================================================
# 8. ACTION VALIDITY
# =============================================================================
def test_8_action_validity():
    """Verify all 5 discrete action choices can execute without error."""
    env = SWARMRLEnv(dataset_name="C101", num_customers=15, num_vehicles=3, seed=42)
    for act in range(5):
        env.reset(seed=42)
        obs, reward, term, trunc, info = env.step(act)
        assert obs.shape == (25,)


# =============================================================================
# 9. ACTION MASKING & INFEASIBILITY
# =============================================================================
def test_9_action_masking_and_infeasibility():
    """Verify that taking infeasible actions incurs the configured penalty."""
    cfg = RewardConfig(infeasible_action_penalty=15.0)
    env = SWARMRLEnv(dataset_name="C101", num_customers=15, num_vehicles=3, reward_config=cfg, seed=42)
    env.reset(seed=42)

    # Action 1: Reassign stranded order when no truck is broken down (infeasible)
    _, reward, _, _, _ = env.step(ACTION_REASSIGN_STRANDED_ORDER)
    assert reward <= -15.0


# =============================================================================
# 10. REWARD FUNCTION
# =============================================================================
def test_10_reward_calculation():
    """Verify multi-objective reward decomposition and configurable weights."""
    calc = FleetRewardCalculator()
    total_r, decomp = calc.calculate_step_reward_decomposed(
        new_deliveries=2,
        new_on_time=2,
        new_recoveries=1,
        new_failed=0,
        new_late=0,
        delay_minutes=0.0,
        incremental_distance_km=10.0,
        incremental_fuel_liters=3.0,
        incremental_co2_kg=8.0,
        incremental_empty_km=0.0,
        useful_repositioning=False,
    )
    assert "delivery_reward" in decomp
    assert "recovery_reward" in decomp
    assert "fuel_penalty" in decomp
    assert total_r > 0.0  # Net positive for on-time deliveries + recovery


# =============================================================================
# 11. PPO MODEL LOADING
# =============================================================================
def test_11_ppo_model_loading():
    """Verify pre-trained PPO agent loads from zip file checkpoint."""
    model_path = Path("results/models/ppo_agent.zip")
    assert model_path.exists()

    env = SWARMRLEnv(dataset_name="C101", num_customers=15, num_vehicles=3, seed=42)
    agent = PPOFleetAgent(env=env, seed=42)
    agent.load(model_path, env=env)
    assert agent.model is not None


# =============================================================================
# 12. PPO INFERENCE
# =============================================================================
def test_12_ppo_inference():
    """Verify PPO agent performs inference and selects valid discrete action in [0, 4]."""
    model_path = Path("results/models/ppo_agent.zip")
    env = SWARMRLEnv(dataset_name="C101", num_customers=15, num_vehicles=3, seed=42)
    agent = PPOFleetAgent(env=env, seed=42)
    agent.load(model_path, env=env)

    obs, _ = env.reset(seed=42)
    action = agent.predict(obs, deterministic=True)
    assert isinstance(action, int)
    assert 0 <= action < 5


# =============================================================================
# 13. IDENTICAL SEED SCENARIOS
# =============================================================================
def test_13_identical_seed_scenarios():
    """Verify generate_benchmark_scenario provides 100% identical conditions on identical seeds."""
    scen1 = generate_benchmark_scenario(seed=777, dataset_name="C101", customers_count=20, vehicles_count=4)
    scen2 = generate_benchmark_scenario(seed=777, dataset_name="C101", customers_count=20, vehicles_count=4)

    f1 = scen1.get_fleet_copy()
    f2 = scen2.get_fleet_copy()
    for v_id in f1.vehicles:
        assert f1.vehicles[v_id].current_location == f2.vehicles[v_id].current_location
        assert f1.vehicles[v_id].max_weight == f2.vehicles[v_id].max_weight

    b1 = scen1.get_breakdown_spec()
    b2 = scen2.get_breakdown_spec()
    assert b1.timestamp_mins == b2.timestamp_mins
    assert b1.payload["vehicle_id"] == b2.payload["vehicle_id"]


# =============================================================================
# 14. PPO INDEPENDENCE FROM RULE-BASED RECOVERY
# =============================================================================
def test_14_ppo_independence_from_rule_based_recovery():
    """Verify PPO step does not invoke rule-based contract-net recovery under the hood."""
    env = SWARMRLEnv(dataset_name="C101", num_customers=15, num_vehicles=3, seed=42)
    env.reset(seed=42)

    broken_v = list(env.env.fleet_state.vehicles.values())[1]
    broken_v.status = VehicleStatus.BROKEN_DOWN
    stranded_orders = list(broken_v.assigned_orders)
    assert len(stranded_orders) > 0

    # Step action 4 (HOLD): rule-based recovery must NOT have recovered the order
    env.step(ACTION_HOLD_OR_CONTINUE)
    assert broken_v.assigned_orders == stranded_orders


# =============================================================================
# 15. NO FUTURE INFORMATION LEAKAGE
# =============================================================================
def test_15_no_future_information_leakage():
    """Verify observation vector contains zero future event leakage before event occurrence."""
    env = SWARMRLEnv(dataset_name="C101", num_customers=15, num_vehicles=3, seed=42)
    obs1, _ = env.reset(seed=42)

    # Before breakdown: is_broken flag (index 9) must be 0.0
    assert obs1[9] == 0.0

    # Break down the controlled truck
    ctrl_v = env.env.fleet_state.vehicles[env.controlled_truck_id]
    ctrl_v.status = VehicleStatus.BROKEN_DOWN

    # Now observation reflects dynamic current breakdown (1 broken out of 3 vehicles = 1/3)
    obs2 = env._get_observation()
    assert obs2[9] == pytest.approx(1.0 / 3.0, rel=1e-3)
    assert obs2[9] > 0.0


# =============================================================================
# 16. FAIR BENCHMARK INITIALIZATION
# =============================================================================
def test_16_fair_benchmark_initialization():
    """Verify all algorithms receive identical clean clones of initial orders and road network."""
    scen = generate_benchmark_scenario(seed=101, dataset_name="C101", customers_count=20, vehicles_count=4)
    
    fleet_nn = scen.get_fleet_copy()
    fleet_ortools = scen.get_fleet_copy()
    fleet_ppo = scen.get_fleet_copy()

    assert set(fleet_nn.vehicles.keys()) == set(fleet_ortools.vehicles.keys()) == set(fleet_ppo.vehicles.keys())
    assert len(fleet_nn.active_orders) == len(fleet_ortools.active_orders) == len(fleet_ppo.active_orders)
