"""
Offline Training Script for SWARMRoute Trajectory Temporal Transformer.
Trains TrajectoryTemporalTransformer on multi-step operational fleet sequences
to predict trajectory trends: speed variation, fuel drain rate, schedule delay risk,
and corridor reroute desirability.
Saves checkpoint to results/models/temporal_transformer.pt with validation metrics.
"""
from __future__ import annotations

import json
import math
import os
from pathlib import Path
import random
from typing import Dict, List, Tuple
import numpy as np

try:
    import torch
    import torch.nn as nn
    from torch.utils.data import DataLoader, TensorDataset
except ImportError:
    raise ImportError("PyTorch is required to train the TrajectoryTemporalTransformer.")

from src.ai.temporal_transformer import TrajectoryTemporalTransformer


def generate_trajectory_dataset(
    num_samples: int = 1200,
    seq_len: int = 6,
    feature_dim: int = 12,
    seed: int = 42,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Generates realistic trajectory sequence dataset based on vehicle dynamics:
    - Speed variations with traffic friction
    - Fuel depletion as distance accumulates
    - Schedule delay accumulation under congested conditions
    """
    rng = np.random.RandomState(seed)
    X = np.zeros((num_samples, seq_len, feature_dim), dtype=np.float32)
    y = np.zeros((num_samples, 4), dtype=np.float32)  # [speed_trend, fuel_drain, delay_risk, reroute_desirability]

    for i in range(num_samples):
        # Base vehicle parameters
        base_speed = rng.uniform(20.0, 60.0) / 100.0  # speed_norm
        fuel_start = rng.uniform(0.4, 1.0)
        traffic_base = rng.uniform(0.1, 0.8)
        lat = rng.uniform(12.8, 13.1) / 90.0
        lon = rng.uniform(77.4, 77.7) / 180.0
        
        # Trajectory scenario: 0: normal, 1: heavy traffic slowdown, 2: fuel critical drain
        scenario = rng.choice([0, 1, 2], p=[0.5, 0.3, 0.2])

        for t in range(seq_len):
            if scenario == 1:
                # Speed drops, traffic and delay risk rise
                speed_t = max(0.05, base_speed - (t * 0.05) + rng.normal(0, 0.01))
                traffic_t = min(1.0, traffic_base + (t * 0.1))
                fuel_t = max(0.0, fuel_start - (t * 0.01))
                urgency_t = min(1.5, 0.5 + (t * 0.1))
            elif scenario == 2:
                # Fast fuel drain rate
                speed_t = base_speed + rng.normal(0, 0.02)
                traffic_t = traffic_base
                fuel_t = max(0.0, fuel_start - (t * 0.05))
                urgency_t = 0.5
            else:
                # Normal progression
                speed_t = base_speed + rng.normal(0, 0.02)
                traffic_t = traffic_base + rng.normal(0, 0.02)
                fuel_t = max(0.0, fuel_start - (t * 0.015))
                urgency_t = 0.5

            X[i, t, 0] = np.clip(lat + (t * 0.001), -1.0, 1.0)
            X[i, t, 1] = np.clip(lon + (t * 0.001), -1.0, 1.0)
            X[i, t, 2] = np.clip(speed_t, 0.0, 1.5)
            X[i, t, 3] = np.clip(rng.uniform(0.0, 1.0), 0.0, 1.0)  # heading
            X[i, t, 4] = np.clip(fuel_t, 0.0, 1.0)
            X[i, t, 5] = np.clip(traffic_t, 0.0, 1.0)
            X[i, t, 6] = 0.15 if traffic_t > 0.6 else 0.05  # road friction
            X[i, t, 7] = np.clip(0.3 + (t * 0.02), 0.0, 2.0)  # eta norm
            X[i, t, 8] = np.clip(t / seq_len, 0.0, 1.0)  # progress
            X[i, t, 9] = np.clip(urgency_t, 0.0, 2.0)
            X[i, t, 10] = 1.0  # cloud connectivity
            X[i, t, 11] = 0.95  # condition

        # Target dynamic indicators computed from sequence trend
        speed_delta = X[i, -1, 2] - X[i, 0, 2]
        fuel_drain = X[i, 0, 4] - X[i, -1, 4]
        traffic_final = X[i, -1, 5]
        
        delay_risk = 0.8 if (traffic_final > 0.6 and speed_delta < -0.1) else 0.1
        reroute_desirability = 1.0 if delay_risk > 0.5 else 0.0

        y[i, 0] = speed_delta
        y[i, 1] = fuel_drain
        y[i, 2] = delay_risk
        y[i, 3] = reroute_desirability

    return X, y


def train_temporal_transformer(
    output_dir: str = "results/models",
    epochs: int = 15,
    batch_size: int = 32,
    learning_rate: float = 1e-3,
) -> Dict[str, Any]:
    """Trains and saves the TrajectoryTemporalTransformer checkpoint."""
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    print("[Transformer Training] Generating trajectory sequence dataset...")
    X, y = generate_trajectory_dataset(num_samples=1200)

    # 80/20 train/validation split
    n_train = int(len(X) * 0.8)
    X_train, y_train = torch.from_numpy(X[:n_train]), torch.from_numpy(y[:n_train])
    X_val, y_val = torch.from_numpy(X[n_train:]), torch.from_numpy(y[n_train:])

    train_loader = DataLoader(TensorDataset(X_train, y_train), batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(TensorDataset(X_val, y_val), batch_size=batch_size, shuffle=False)

    model = TrajectoryTemporalTransformer()
    optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate, weight_decay=1e-4)
    criterion = nn.MSELoss()

    print(f"[Transformer Training] Training on {n_train} sequences for {epochs} epochs...")
    history = {"train_loss": [], "val_loss": []}

    for epoch in range(1, epochs + 1):
        model.train()
        total_train_loss = 0.0
        for batch_x, batch_y in train_loader:
            optimizer.zero_grad()
            _, pred_trends = model(batch_x)
            loss = criterion(pred_trends, batch_y)
            loss.backward()
            optimizer.step()
            total_train_loss += loss.item() * len(batch_x)

        avg_train_loss = total_train_loss / n_train

        model.eval()
        total_val_loss = 0.0
        with torch.no_grad():
            for batch_x, batch_y in val_loader:
                _, pred_trends = model(batch_x)
                loss = criterion(pred_trends, batch_y)
                total_val_loss += loss.item() * len(batch_x)

        avg_val_loss = total_val_loss / len(X_val)
        history["train_loss"].append(round(avg_train_loss, 5))
        history["val_loss"].append(round(avg_val_loss, 5))

        if epoch % 5 == 0 or epoch == epochs:
            print(f"  Epoch {epoch:02d}/{epochs:02d} | Train Loss: {avg_train_loss:.5f} | Val Loss: {avg_val_loss:.5f}")

    # Save model weights
    ckpt_path = Path(output_dir) / "temporal_transformer.pt"
    torch.save(model.state_dict(), ckpt_path)
    print(f"[Transformer Training] Model checkpoint successfully saved to {ckpt_path}")

    # Save training metrics report
    metrics = {
        "model": "TrajectoryTemporalTransformer",
        "seq_len": TrajectoryTemporalTransformer.SEQ_LEN,
        "input_dim": TrajectoryTemporalTransformer.INPUT_DIM,
        "hidden_dim": TrajectoryTemporalTransformer.HIDDEN_DIM,
        "parameters_count": sum(p.numel() for p in model.parameters()),
        "final_train_loss": history["train_loss"][-1],
        "final_val_loss": history["val_loss"][-1],
        "epochs": epochs,
        "checkpoint": str(ckpt_path),
        "status": "VALIDATED",
    }
    metrics_path = Path(output_dir) / "transformer_metrics.json"
    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)

    return metrics


if __name__ == "__main__":
    metrics = train_temporal_transformer()
    print("Training Complete:", json.dumps(metrics, indent=2))
