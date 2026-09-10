#!/usr/bin/env python3
"""
Model Training Script for SWARMRoute Predictors (Layer A)
Trains Travel-Time, ML-Fuel, and Customer Demand prediction models.
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.prediction.travel_time import TravelTimePredictor
from src.prediction.fuel_ml import FuelConsumptionPredictor
from src.prediction.demand import DemandPredictor


def train_travel_time_model(samples: int = 50000, seed: int = 42, output_dir: str = "results/models") -> None:
    print("====================================================")
    print(" TRAINING: Travel-Time Prediction Model (Layer A)")
    print("====================================================")
    print(f"Generating synthetic trip observations ({samples:,} samples, seed={seed})...")
    X, y = TravelTimePredictor.generate_synthetic_trip_data(num_samples=samples, seed=seed)
    print(f"Training dataset shape: {X.shape} features, {len(y)} labels")

    model = TravelTimePredictor(random_state=seed)
    metrics = model.train(X, y)

    print("\nModel Evaluation (Validation Set):")
    print(f"  MAE:       {metrics['mae']} hrs ({metrics['mae']*60:.2f} mins)")
    print(f"  RMSE:      {metrics['rmse']} hrs ({metrics['rmse']*60:.2f} mins)")
    print(f"  R² Score:  {metrics['r2_score']:.4f}")

    out_path = Path(output_dir) / "travel_time.joblib"
    model.save(out_path)
    print(f"\nModel checkpoint successfully saved to {out_path}")


def train_fuel_model(samples: int = 50000, seed: int = 42, output_dir: str = "results/models") -> None:
    print("====================================================")
    print(" TRAINING: ML Fuel Consumption Model (Layer A)")
    print("====================================================")
    print(f"Generating simulated fleet trips ({samples:,} samples, seed={seed})...")
    X, y = FuelConsumptionPredictor.generate_synthetic_fuel_data(num_samples=samples, seed=seed)
    print(f"Dataset shape: {X.shape} features, {len(y)} labels")

    model = FuelConsumptionPredictor(random_state=seed)
    metrics = model.train(X, y)

    print("\nModel Evaluation:")
    print(f"  ML Model MAE:        {metrics['ml_mae']} L")
    print(f"  ML Model RMSE:       {metrics['ml_rmse']} L")
    print(f"  ML Model R² Score:   {metrics['ml_r2_score']:.4f}")
    print(f"  Physics Baseline MAE: {metrics['physics_mae']} L")
    print(f"  Physics Baseline RMSE: {metrics['physics_rmse']} L")

    out_path = Path(output_dir) / "fuel.joblib"
    model.save(out_path)
    print(f"\nModel checkpoint successfully saved to {out_path}")


def train_demand_model(samples: int = 50000, seed: int = 42, output_dir: str = "results/models") -> None:
    print("====================================================")
    print(" TRAINING: Customer Demand Forecasting Model (Layer A)")
    print("====================================================")
    print(f"Generating dynamic demand series ({samples:,} samples, seed={seed})...")
    X, y = DemandPredictor.generate_synthetic_demand_data(num_samples=samples, seed=seed)
    print(f"Dataset shape: {X.shape} features, {len(y)} labels")

    model = DemandPredictor(random_state=seed)
    metrics = model.train(X, y)

    print("\nModel Evaluation:")
    print(f"  ML Model MAE:          {metrics['ml_mae']} units")
    print(f"  ML Model RMSE:         {metrics['ml_rmse']} units")
    print(f"  ML Model R² Score:     {metrics['ml_r2_score']:.4f}")
    print(f"  Historical Baseline MAE: {metrics['baseline_mean_mae']} units")
    print(f"  Historical Baseline RMSE: {metrics['baseline_mean_rmse']} units")

    out_path = Path(output_dir) / "demand.joblib"
    model.save(out_path)
    print(f"\nModel checkpoint successfully saved to {out_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Train SWARMRoute predictive models.")
    parser.add_argument(
        "--model",
        choices=["travel_time", "fuel", "demand", "all"],
        default="all",
        help="Which model to train",
    )
    parser.add_argument(
        "--samples",
        type=int,
        default=50000,
        help="Number of training samples (default: 50,000 for high accuracy)",
    )
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--output-dir", default="results/models", help="Folder to save checkpoints")
    args = parser.parse_args()

    if args.model in ("travel_time", "all"):
        train_travel_time_model(samples=args.samples, seed=args.seed, output_dir=args.output_dir)
    if args.model in ("fuel", "all"):
        train_fuel_model(samples=args.samples, seed=args.seed, output_dir=args.output_dir)
    if args.model in ("demand", "all"):
        train_demand_model(samples=args.samples, seed=args.seed, output_dir=args.output_dir)


if __name__ == "__main__":
    main()
