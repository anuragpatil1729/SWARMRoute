import pytest
import numpy as np
from src.rl.environment import SWARMRLEnv, RewardConfig


def test_gym_environment_initialization_and_reset():
    env = SWARMRLEnv(dataset_name="C101", num_customers=15, num_vehicles=3, seed=42)
    obs, info = env.reset(seed=42)

    assert isinstance(obs, np.ndarray)
    assert obs.shape == (SWARMRLEnv.OBS_DIM,)
    assert not np.isnan(obs).any()
    assert not np.isinf(obs).any()
    assert "controlled_truck" in info
    assert env.action_space.n == 5


def test_gym_environment_step_cycle():
    env = SWARMRLEnv(dataset_name="C101", num_customers=15, num_vehicles=3, seed=42)
    obs, info = env.reset(seed=42)

    # Step action 4: HOLD_OR_CONTINUE
    next_obs, reward, terminated, truncated, step_info = env.step(4)

    assert isinstance(next_obs, np.ndarray)
    assert next_obs.shape == (SWARMRLEnv.OBS_DIM,)
    assert isinstance(reward, float)
    assert isinstance(terminated, bool)
    assert isinstance(truncated, bool)
    assert "total_distance_km" in step_info
    assert "delivered_orders" in step_info


def test_gym_environment_infeasible_penalty():
    # Configure custom penalty
    cfg = RewardConfig(infeasible_action_penalty=12.5)
    env = SWARMRLEnv(dataset_name="C101", num_customers=15, num_vehicles=3, reward_config=cfg, seed=42)
    obs, info = env.reset(seed=42)

    # Action 1: REASSIGN_STRANDED_ORDER when no truck is broken down (infeasible)
    next_obs, reward, terminated, truncated, step_info = env.step(1)
    # Reward must include the infeasible penalty (-12.5)
    assert reward <= -12.5


def test_observation_dimension_contract():
    """Strict regression test ensuring observation space is exactly 25-dimensional."""
    env = SWARMRLEnv(dataset_name="C101", num_customers=15, num_vehicles=3, seed=42)
    obs, info = env.reset(seed=42)
    
    # Fundamental dimension contract
    assert SWARMRLEnv.OBS_DIM == 25
    assert env.observation_space.shape == (25,)
    assert obs.shape == (25,)
    assert len(obs) == 25
    
    # Check that each feature element is finite and within physical bounds
    # [0] t_norm (0..2)
    assert 0.0 <= obs[0] <= 2.0
    # [1, 2] x_norm, y_norm (0..1)
    assert 0.0 <= obs[1] <= 1.0
    assert 0.0 <= obs[2] <= 1.0
    # [3] cap_rem_norm (0..1)
    assert 0.0 <= obs[3] <= 1.0
    # [4] load_norm (0..1)
    assert 0.0 <= obs[4] <= 1.0
    # [5] fuel_norm (0..1)
    assert 0.0 <= obs[5] <= 1.0
    # [6] traffic_norm (0..1)
    assert 0.0 <= obs[6] <= 1.0
    # [7] stranded_norm (0..1)
    assert 0.0 <= obs[7] <= 1.0
    # [8] avail_norm (0..1)
    assert 0.0 <= obs[8] <= 1.0
    # [9] broken_norm (0..1)
    assert 0.0 <= obs[9] <= 1.0
    # [10] mesh_neighbors_norm (0..1)
    assert 0.0 <= obs[10] <= 1.0
    # [11] conn_code (0, 0.5, 1.0)
    assert obs[11] in (0.0, 0.5, 1.0)
    # [12] pred_demand_norm (0..1)
    assert 0.0 <= obs[12] <= 1.0
    # [13] route_prog_norm (0..1)
    assert 0.0 <= obs[13] <= 1.0
    # [14] rem_stops_norm (0..2)
    assert 0.0 <= obs[14] <= 2.0
    # [15] urgency_norm (-1..2)
    assert -1.0 <= obs[15] <= 2.0
    # [16..24] 3 candidates * 3 features = 9 features
    cand_features = obs[16:25]
    assert len(cand_features) == 9
    assert not np.isnan(cand_features).any()


def test_action_masks_structure_and_behavior():
    """Verify that action_masks() accurately captures structural feasibility."""
    from src.models.vehicle import VehicleStatus

    env = SWARMRLEnv(dataset_name="C101", num_customers=15, num_vehicles=3, seed=42)
    env.reset(seed=42)

    masks = env.action_masks()
    assert isinstance(masks, np.ndarray)
    assert masks.shape == (5,)
    assert masks.dtype == bool

    # Initial state: Action 4 (HOLD) and Action 2 (ACCEPT/REJECT) must be True
    assert bool(masks[4]) is True
    assert bool(masks[2]) is True

    # No broken vehicles initially -> Action 1 (REASSIGN) must be False
    assert bool(masks[1]) is False

    # Simulate a breakdown on TRUCK_01 with assigned orders
    truck1 = env.env.fleet_state.vehicles.get("TRUCK_01")
    truck2 = env.env.fleet_state.vehicles.get("TRUCK_02")
    if truck1 and truck2 and len(truck1.assigned_orders) > 0:
        truck1.status = VehicleStatus.BROKEN_DOWN
        first_order = env.env.fleet_state.active_orders.get(truck1.assigned_orders[0])
        if first_order:
            truck2.current_load = 0.0
            masks_post = env.action_masks()
            assert bool(masks_post[1]) is True

