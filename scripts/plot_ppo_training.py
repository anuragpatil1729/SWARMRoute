#!/usr/bin/env python3
"""
Plot PPO Training Curves
Visualizes the 6 training metrics recorded during reinforcement learning:
1. Episode Cumulative Reward
2. Delivery Success Rate (%)
3. Total Fuel Consumed (Liters)
4. Total CO2 Emissions (kg)
5. Late Deliveries Count
6. Self-Healing Recovery Latency (sec)
Saves publication figure to results/plots/ppo_training_curves.png.
"""
import json
import sys
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def plot_ppo_training(
    metrics_path: str = "results/logs/ppo_training_metrics.json",
    output_path: str = "results/plots/ppo_training_curves.png",
) -> None:
    in_path = Path(metrics_path)
    if not in_path.exists():
        print(f"Metrics file not found: {metrics_path}")
        return

    with open(in_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    rewards = data.get("episode_rewards", [])
    success = data.get("delivery_success_rates", [])
    fuel = data.get("fuel_consumed", [])
    co2 = data.get("co2_emissions", [])
    late = data.get("late_deliveries", [])
    rec_times = data.get("recovery_times", [])

    episodes = np.arange(1, len(rewards) + 1)

    fig, axes = plt.subplots(2, 3, figsize=(16, 9), facecolor="#0f172a")
    plt.subplots_adjust(hspace=0.35, wspace=0.25)

    plot_configs = [
        (axes[0, 0], rewards, "Episode Cumulative Reward", "Episode", "Reward", "#38bdf8", "o-"),
        (axes[0, 1], success, "Delivery Success Rate (%)", "Episode", "Success %", "#34d399", "s-"),
        (axes[0, 2], fuel, "Total Fuel Consumed (Liters)", "Episode", "Fuel (L)", "#f59e0b", "^-"),
        (axes[1, 0], co2, "Total CO2 Emissions (kg)", "Episode", "CO2 (kg)", "#ef4444", "d-"),
        (axes[1, 1], late, "Late Deliveries Count", "Episode", "Count", "#a855f7", "v-"),
        (axes[1, 2], rec_times, "Recovery Latency (sec)", "Episode", "Time (s)", "#22d3ee", "p-"),
    ]

    for ax, vals, title, xlabel, ylabel, color, marker in plot_configs:
        ax.set_facecolor("#1e293b")
        y = np.array(vals) if vals else np.zeros(len(episodes))
        ax.plot(episodes, y, marker, color=color, linewidth=2, markersize=6, label="Trained PPO")

        # Running average smoothing if >= 4 episodes
        if len(y) >= 4:
            smooth = np.convolve(y, np.ones(3)/3, mode='valid')
            smooth_x = episodes[len(episodes) - len(smooth):]
            ax.plot(smooth_x, smooth, "--", color="#ffffff", alpha=0.6, label="Trend (MA-3)")

        ax.set_title(title, fontsize=12, fontweight="bold", color="#f8fafc", pad=10)
        ax.set_xlabel(xlabel, fontsize=10, color="#94a3b8")
        ax.set_ylabel(ylabel, fontsize=10, color="#94a3b8")
        ax.tick_params(colors="#cbd5e1", labelsize=9)
        ax.grid(True, linestyle="--", alpha=0.2, color="#94a3b8")
        for spine in ax.spines.values():
            spine.set_edgecolor("#334155")
        ax.legend(loc="best", framealpha=0.3, labelcolor="#e2e8f0", fontsize=8)

    suptitle = f"SWARMRoute PPO Reinforcement Learning Training Dynamics ({data.get('dataset', 'C101')})"
    fig.suptitle(suptitle, fontsize=16, fontweight="heavy", color="#f8fafc", y=0.98)

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=200, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close()
    print(f"Generated PPO training curves plot: {output_path}")


if __name__ == "__main__":
    plot_ppo_training()
