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
