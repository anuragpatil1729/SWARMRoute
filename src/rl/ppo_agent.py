from __future__ import annotations
import os
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
import numpy as np

# Prevent PyTorch / Keras C-extension collisions on macOS Python 3.13
for _m in ("tensorflow", "keras", "tensorboard"):
    if _m not in sys.modules:
        sys.modules[_m] = None

try:
    from stable_baselines3 import PPO
    from stable_baselines3.common.callbacks import BaseCallback
    from stable_baselines3.common.evaluation import evaluate_policy
except ImportError:
    PPO = None
    BaseCallback = object

from src.rl.environment import SWARMRLEnv


class TrainingMetricsLogger(BaseCallback):
    """Callback for tracking training rewards, losses, and episode outcomes."""
    def __init__(self, verbose: int = 0) -> None:
        super().__init__(verbose)
        self.episode_rewards: List[float] = []
        self.episode_lengths: List[int] = []
        self.delivery_success_rates: List[float] = []
        self.on_time_rates: List[float] = []
        self.fuel_consumed: List[float] = []
        self.co2_emissions: List[float] = []
        self.late_deliveries: List[int] = []
        self.distances: List[float] = []
        self.recoveries: List[int] = []
        self.failed_orders: List[int] = []
        self.recovery_times: List[float] = []
        self.current_reward = 0.0
        self.current_length = 0

    def _on_step(self) -> bool:
        reward = self.locals.get("rewards", [0.0])[0]
        done = self.locals.get("dones", [False])[0]

        self.current_reward += float(reward)
        self.current_length += 1

        if done:
            self.episode_rewards.append(round(self.current_reward, 2))
            self.episode_lengths.append(self.current_length)
            self.current_reward = 0.0
            self.current_length = 0

            infos = self.locals.get("infos", [{}])[0]
            deliv = infos.get("delivered_orders", 0)
            failed = infos.get("failed_orders", 0)
            late = int(infos.get("late_orders", 0))
            total = max(1, deliv + failed)

            succ_pct = round((deliv / total) * 100.0, 1)
            on_time = max(0, deliv - late)
            ontime_pct = round((on_time / total) * 100.0, 1)

            self.delivery_success_rates.append(succ_pct)
            self.on_time_rates.append(ontime_pct)
            self.fuel_consumed.append(round(infos.get("total_fuel_liters", 0.0), 2))
            self.co2_emissions.append(round(infos.get("total_co2_kg", 0.0), 2))
            self.late_deliveries.append(late)
            self.distances.append(round(infos.get("total_distance_km", 0.0), 2))
            self.recoveries.append(int(infos.get("recoveries_count", 0)))
            self.failed_orders.append(failed)
            self.recovery_times.append(round(infos.get("recovery_time_sec", 0.0), 4))

        return True


class PPOFleetAgent:
    """
    Stable-Baselines3 PPO Reinforcement Learning Policy for Autonomous Fleet Decision Making.
    Trained on the realistic Gymnasium SWARMRLEnv.
    Supports reproducible seeds, model checkpointing, and evaluation.
    """
    def __init__(
        self,
        env: Optional[SWARMRLEnv] = None,
        learning_rate: float = 3e-4,
        n_steps: int = 64,
        batch_size: int = 32,
        n_epochs: int = 4,
        gamma: float = 0.99,
        gae_lambda: float = 0.95,
        clip_range: float = 0.2,
        seed: int = 42,
        device: str = "cpu",
    ) -> None:
        if PPO is None:
            raise ImportError("stable_baselines3 is required to use PPOFleetAgent.")

        self.env = env
        self.seed = seed
        self.model: Optional[PPO] = None
        self.logger_callback = TrainingMetricsLogger()

        if env is not None:
            self.model = PPO(
                policy="MlpPolicy",
                env=self.env,
                learning_rate=learning_rate,
                n_steps=n_steps,
                batch_size=batch_size,
                n_epochs=n_epochs,
                gamma=gamma,
                gae_lambda=gae_lambda,
                clip_range=clip_range,
                seed=seed,
                device=device,
                verbose=0,
            )

    def train(self, total_timesteps: int = 1000) -> Dict[str, Any]:
        """Trains the PPO policy on the SWARMRoute environment."""
        if self.model is None:
            raise ValueError("Environment must be provided to train PPO model.")

        self.model.learn(total_timesteps=total_timesteps, callback=self.logger_callback)

        ep_rewards = self.logger_callback.episode_rewards
        mean_reward = float(np.mean(ep_rewards)) if ep_rewards else 0.0
        return {
            "total_timesteps": total_timesteps,
            "episodes_completed": len(ep_rewards),
            "mean_episode_reward": round(mean_reward, 3),
            "episode_rewards": [round(r, 2) for r in ep_rewards[-10:]],
        }

    def predict(self, observation: np.ndarray, deterministic: bool = True) -> int:
        """Selects discrete fleet action given local observation vector."""
        if self.model is None:
            return 4  # Default HOLD_OR_CONTINUE
        action, _ = self.model.predict(observation, deterministic=deterministic)
        return int(action)

    def evaluate(self, env: Optional[SWARMRLEnv] = None, num_episodes: int = 3) -> Dict[str, float]:
        """Runs deterministic evaluation across episodes."""
        eval_env = env or self.env
        if eval_env is None or self.model is None:
            return {"mean_reward": 0.0, "std_reward": 0.0}

        episode_rewards = []
        episode_deliveries = []

        for _ in range(num_episodes):
            obs, info = eval_env.reset()
            done = False
            total_r = 0.0

            while not done:
                action = self.predict(obs, deterministic=True)
                obs, r, term, trunc, step_info = eval_env.step(action)
                total_r += r
                done = term or trunc

            episode_rewards.append(total_r)
            episode_deliveries.append(step_info.get("delivered_orders", 0))

        return {
            "mean_reward": round(float(np.mean(episode_rewards)), 2),
            "std_reward": round(float(np.std(episode_rewards)), 2),
            "mean_deliveries": round(float(np.mean(episode_deliveries)), 1),
        }

    def save(self, path: Union[str, Path]) -> None:
        if self.model is not None:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            self.model.save(str(path))

    def load(self, path: Union[str, Path], env: Optional[SWARMRLEnv] = None) -> None:
        self.model = PPO.load(str(path), env=env)
