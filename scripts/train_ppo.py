#!/usr/bin/env python3
"""
PPO Training CLI Script for SWARMRoute
Trains a Stable-Baselines3 PPO policy on the realistic SWARMRLEnv.
Saves model checkpoint to results/models/ppo_agent.zip.
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

# Ensure project root in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Safeguard against ARM64 pyarrow and PyTorch/Keras collision on Python 3.13
for _m in ("pyarrow", "tensorflow", "keras", "tensorboard"):
    if _m not in sys.modules:
        sys.modules[_m] = None

from src.rl.environment import SWARMRLEnv
from src.rl.ppo_agent import PPOFleetAgent


def train_ppo_cli(
    dataset: str = "C101",
    timesteps: int = 1500,
    seed: int = 42,
    customers: int = 20,
    vehicles: int = 5,
    eval_episodes: int = 5,
    masking: bool = True,
    save_path: str = "results/models/ppo_agent.zip",
    metrics_path: str = "results/logs/ppo_training_metrics.json",
) -> None:
    print("================================================================================")
    print(" SWARMRoute: PPO REINFORCEMENT LEARNING TRAINING")
    print(f" Dataset: Solomon {dataset} ({customers} customers, {vehicles} vehicles)")
    print(f" Timesteps: {timesteps} | Seed: {seed} | Policy: MlpPolicy (PPO)")
    print("================================================================================")

    # Pre-load ML prediction models if available
    from src.prediction.travel_time import TravelTimePredictor
    from src.prediction.fuel_ml import FuelConsumptionPredictor
    from src.prediction.demand import DemandPredictor

    tt_pred = TravelTimePredictor(random_state=seed)
    tt_path = Path("results/models/travel_time.joblib")
    if tt_path.exists():
        tt_pred.load(tt_path)

    fuel_pred = FuelConsumptionPredictor(random_state=seed)
    fuel_path = Path("results/models/fuel.joblib")
    if fuel_path.exists():
        fuel_pred.load(fuel_path)

    demand_pred = DemandPredictor(random_state=seed)
    demand_path = Path("results/models/demand.joblib")
    if demand_path.exists():
        demand_pred.load(demand_path)

    env = SWARMRLEnv(
        dataset_name=dataset,
        num_customers=customers,
        num_vehicles=vehicles,
        step_size_mins=2.0,
        max_steps=150,
        seed=seed,
        travel_time_predictor=tt_pred,
        fuel_predictor=fuel_pred,
        demand_predictor=demand_pred,
    )

    agent = PPOFleetAgent(env=env, use_masking=masking, seed=seed)

    print(f"\nTraining PPO Agent (Action Masking: {agent.use_masking})...")
    train_results = agent.train(total_timesteps=timesteps)

    print("\nTraining Complete:")
    print(f"  Total Timesteps:     {train_results['total_timesteps']}")
    print(f"  Episodes Finished:   {train_results['episodes_completed']}")
    print(f"  Mean Episode Reward: {train_results['mean_episode_reward']:.2f}")

    # Evaluate trained policy
    print(f"\nRunning Evaluation ({eval_episodes} episodes)...")
    eval_metrics = agent.evaluate(num_episodes=eval_episodes)
    print(f"  Mean Eval Reward:    {eval_metrics['mean_reward']:.2f} +/- {eval_metrics['std_reward']:.2f}")
    print(f"  Mean Deliveries:     {eval_metrics['mean_deliveries']:.1f}")

    # Save Model
    Path(save_path).parent.mkdir(parents=True, exist_ok=True)
    agent.save(save_path)
    print(f"\nSaved trained PPO model checkpoint to: {save_path}")

    # Save Training Log
    Path(metrics_path).parent.mkdir(parents=True, exist_ok=True)
    log_data = {
        "dataset": dataset,
        "seed": seed,
        "timesteps": timesteps,
        "masking": agent.use_masking,
        "train_metrics": train_results,
        "eval_metrics": eval_metrics,
        "episode_rewards": agent.logger_callback.episode_rewards,
        "delivery_success_rates": agent.logger_callback.delivery_success_rates,
        "on_time_rates": agent.logger_callback.on_time_rates,
        "fuel_consumed": agent.logger_callback.fuel_consumed,
        "co2_emissions": agent.logger_callback.co2_emissions,
        "distances": agent.logger_callback.distances,
        "recoveries": agent.logger_callback.recoveries,
        "late_deliveries": agent.logger_callback.late_deliveries,
        "failed_orders": agent.logger_callback.failed_orders,
        "recovery_times": agent.logger_callback.recovery_times,
    }
    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump(log_data, f, indent=2)
    print(f"Saved training metrics log to: {metrics_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Train PPO policy for SWARMRoute.")
    parser.add_argument("--dataset", default="C101", help="Solomon benchmark instance")
    parser.add_argument("--timesteps", type=int, default=50000, help="Total training timesteps")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--customers", type=int, default=20, help="Number of customers")
    parser.add_argument("--vehicles", type=int, default=5, help="Number of vehicles")
    parser.add_argument("--eval", type=int, default=5, help="Evaluation episodes")
    parser.add_argument("--masking", action=argparse.BooleanOptionalAction, default=True, help="Use invalid action masking")
    parser.add_argument("--save-path", default="results/models/ppo_agent.zip", help="Path to save PPO zip model")
    parser.add_argument("--metrics-path", default="results/logs/ppo_training_metrics.json", help="Path to save metrics json")
    args = parser.parse_args()

    train_ppo_cli(
        dataset=args.dataset,
        timesteps=args.timesteps,
        seed=args.seed,
        customers=args.customers,
        vehicles=args.vehicles,
        eval_episodes=args.eval,
        masking=args.masking,
        save_path=args.save_path,
        metrics_path=args.metrics_path,
    )


if __name__ == "__main__":
    main()
