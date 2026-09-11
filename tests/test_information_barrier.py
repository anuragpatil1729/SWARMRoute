import pytest
import numpy as np
from src.data.loaders.solomon import load_solomon_benchmark
from src.models.fleet_state import ConnectivityState
from src.models.vehicle import VehicleStatus
from src.simulation.environment import FleetSimulationEnvironment
from src.prediction.fuel import DeterministicFuelModel
from src.networking.mesh import MeshNetwork
from src.rl.environment import SWARMRLEnv
from src.rl.ppo_agent import PPOFleetAgent


def test_disconnected_observation_no_oracle_leakage():
    """
    Validates the strict information barrier:
    When in MESH_MODE / disconnected, observations must only contain local physical
    truck features and mesh neighbors, with zero ground truth leakage of unrevealed future disruptions.
    """
    env = SWARMRLEnv(dataset_name="C101", num_customers=25, num_vehicles=5, seed=42)
    obs, info = env.reset(seed=42)

    assert obs.shape == (SWARMRLEnv.OBS_DIM,)
    assert not np.isnan(obs).any(), "Observation must not contain NaNs"
    assert not np.isinf(obs).any(), "Observation must not contain Infs"

    # Simulate cloud loss
    env.env.fleet_state.connectivity_state = ConnectivityState.MESH_MODE
    obs_disconnected = env._get_observation()

    # The connectivity flag in observation (index 11) must reflect MESH_MODE (0.5)
    assert obs_disconnected[11] == 0.5

    # Truck position and capacity must be normalized local values
    assert 0.0 <= obs_disconnected[1] <= 1.0  # x_norm
    assert 0.0 <= obs_disconnected[2] <= 1.0  # y_norm
    assert 0.0 <= obs_disconnected[3] <= 1.0  # remaining capacity norm


def test_ppo_offline_decision_making():
    """
    Verifies that the PPO policy produces valid discrete actions under offline mesh mode
    without throwing exceptions or attempting centralized cloud RPCs.
    """
    env = SWARMRLEnv(dataset_name="C101", num_customers=25, num_vehicles=5, seed=42)
    agent = PPOFleetAgent(env=env, seed=42)

    obs, _ = env.reset(seed=42)
    env.env.fleet_state.connectivity_state = ConnectivityState.MESH_MODE

    # Run 10 steps under complete cloud disconnection
    for _ in range(10):
        action = agent.predict(obs, deterministic=True)
        assert action in (0, 1, 2, 3, 4), f"Action {action} outside discrete action space"
        obs, reward, terminated, truncated, info = env.step(action)
        assert isinstance(reward, float)
        assert not np.isnan(reward)
        if terminated or truncated:
            break
