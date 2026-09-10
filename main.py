#!/usr/bin/env python3
"""
SWARMRoute: Autonomous AI Fleet Optimization Platform
Main CLI entry point.
"""
from __future__ import annotations
import sys
# Prevent pyarrow from registering duplicate C++ protobuf descriptors that conflict with OR-Tools on ARM64
if "pyarrow" not in sys.modules:
    sys.modules["pyarrow"] = None

import argparse
import json
import os
import yaml
from pathlib import Path

# Ensure project root in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.data.loaders.solomon import load_solomon_benchmark
from src.optimization.route_optimizer import RouteOptimizer
from src.evaluation.benchmarks import run_benchmark_comparison
from scripts.download_datasets import (
    download_solomon_instance,
    setup_dynamic_dataset_scaffolding,
    DEFAULT_SOLOMON_INSTANCES,
)


def load_config(config_path: str = "configs/config.yaml") -> dict:
    p = Path(config_path)
    if p.exists():
        with open(p, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    return {}


def cli_download_data(args) -> None:
    """Download required public benchmark datasets."""
    print("====================================================")
    print(" SWARMRoute: Downloading Benchmark Datasets")
    print("====================================================")
    solomon_dir = Path("data/raw/solomon")
    dynamic_dir = Path("data/raw/dynamic")

    instances = args.instances if args.instances else DEFAULT_SOLOMON_INSTANCES
    for inst in instances:
        download_solomon_instance(inst, solomon_dir, force=args.force)

    setup_dynamic_dataset_scaffolding(dynamic_dir)
    print("Download completed.")


def cli_optimize(args) -> None:
    """Run route optimization on a benchmark dataset."""
    config = load_config()
    objective_weights = config.get("optimization", {}).get("objective_weights")

    print(f"Loading dataset '{args.dataset}' ...")
    fleet_state, road_network, metadata = load_solomon_benchmark(
        dataset_name_or_path=args.dataset,
        max_customers=args.customers,
        vehicle_count=args.vehicles,
        raw_dir=config.get("paths", {}).get("data_raw_solomon", "data/raw/solomon"),
    )

    print(
        f"Problem: {metadata['customer_count']} customers | {metadata['vehicle_count']} vehicles | capacity {metadata['vehicle_capacity']}"
    )
    print(f"Solving CVRPTW with OR-Tools (time limit: {args.time_limit}s) ...")

    optimizer = RouteOptimizer(objective_weights=objective_weights)
    result = optimizer.optimize(
        fleet=fleet_state,
        orders=fleet_state.active_orders,
        road_network=road_network,
        time_limit_sec=args.time_limit,
    )

    print("====================================================")
    print(" OPTIMIZATION RESULTS")
    print("====================================================")
    print(f"Status: {result.status}")
    print(f"Active Vehicles: {result.active_vehicles_count} / {len(fleet_state.vehicles)}")
    print(f"Fleet Utilization: {result.fleet_utilization:.1f}%")
    print(f"Total Distance: {result.total_distance:,.2f} km")
    print(f"Total Travel Time: {result.total_travel_time:,.2f} hrs")
    print(f"Total Fuel: {result.total_fuel:,.2f} L")
    print(f"Total CO2: {result.total_emissions:,.2f} kg")
    print(f"Late Deliveries: {result.late_deliveries_count}")
    print(f"Max Lateness: {result.max_lateness:.2f}")
    print(f"Total Objective Cost: ₹{result.total_objective_cost:,.2f}")
    print(f"Computation Time: {result.computation_time_sec:.3f} s")

    print("\nVehicle Routes Summary:")
    for v_id, route in result.routes.items():
        if len(route) > 2:  # non-trivial route
            route_str = " -> ".join(map(str, route))
            print(f"  {v_id} ({len(route)-2} stops): {route_str}")

    if args.output:
        out_p = Path(args.output)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(result.model_dump_json(indent=2), encoding="utf-8")
        print(f"\nSaved full results to {out_p}")


def cli_benchmark(args) -> None:
    """Run baseline vs optimization benchmark comparison."""
    config = load_config()

    dataset_name = args.dataset or "C101"
    fleet_state, road_network, metadata = load_solomon_benchmark(
        dataset_name_or_path=dataset_name,
        max_customers=args.customers,
        vehicle_count=args.vehicles,
        raw_dir=config.get("paths", {}).get("data_raw_solomon", "data/raw/solomon"),
    )

    base_metrics, opt_metrics, improvements = run_benchmark_comparison(
        fleet_state=fleet_state,
        road_network=road_network,
        dataset_name=f"Solomon {dataset_name}",
        time_limit_sec=args.time_limit,
    )

    # Output benchmark report exactly as specified in Section 35
    print("====================================================")
    print("AUTONOMOUS FLEET OPTIMIZATION BENCHMARK")
    print(f"Dataset: Solomon {dataset_name}")
    print(f"Vehicles: {opt_metrics.num_vehicles_used}")
    print(f"Orders: {metadata['customer_count']}")
    print("====================================================")
    print("BASELINE")
    print(f"Distance: {base_metrics.total_distance_km:,.1f} km")
    print(f"Fuel: {base_metrics.total_fuel_liters:,.1f} L")
    print(f"CO2: {base_metrics.total_co2_kg:,.1f} kg")
    print(f"Late deliveries: {base_metrics.late_deliveries}")
    print(f"Cost: ₹{base_metrics.total_cost:,.2f}")
    print(f"Runtime: {base_metrics.runtime_seconds:.2f} sec")
    print("----------------------------------------------------")
    print("AI/DYNAMIC SYSTEM")
    print(f"Distance: {opt_metrics.total_distance_km:,.1f} km")
    print(f"Fuel: {opt_metrics.total_fuel_liters:,.1f} L")
    print(f"CO2: {opt_metrics.total_co2_kg:,.1f} kg")
    print(f"Late deliveries: {opt_metrics.late_deliveries}")
    print(f"Cost: ₹{opt_metrics.total_cost:,.2f}")
    print(f"Recovery time: {opt_metrics.runtime_seconds:.2f} sec")
    print("----------------------------------------------------")
    print("IMPROVEMENT")
    print(f"Fuel reduction: {improvements['fuel_reduction_pct']:.1f} %")
    print(f"CO2 reduction: {improvements['co2_reduction_pct']:.1f} %")
    print(f"Cost reduction: {improvements['cost_reduction_pct']:.1f} %")
    print(f"Late deliveries: {improvements['late_deliveries_reduction_pct']:.1f} %")
    print("====================================================")


def cli_preprocess(args) -> None:
    """Preprocess dynamic multi-period datasets."""
    from src.data.loaders.dynamic import DynamicVRPDataLoader
    print("====================================================")
    print(" PREPROCESSING: Dynamic Multi-Period VRP Datasets")
    print("====================================================")
    loader = DynamicVRPDataLoader()
    # Ensure raw files exist or synthesize from Solomon benchmarks
    if not list(loader.raw_dir.glob("*.json")):
        print("Generating base multi-period instances from Solomon benchmarks...")
        loader.generate_and_save_raw_multiperiod_instance("C101")
        loader.generate_and_save_raw_multiperiod_instance("R101")

    processed = loader.preprocess_dataset()
    print(f"\nSuccessfully preprocessed {len(processed)} dynamic dataset instances:")
    for p in processed:
        content = json.loads(p.read_text(encoding="utf-8"))
        print(
            f"  - {p.name}: {content['num_periods']} periods, {content['total_orders']} dynamic orders (Horizon: {content['total_horizon']:.0f} mins)"
        )
    print("All processed datasets saved to data/processed/")


def cli_train(args) -> None:
    """Train machine learning prediction models (Layer A)."""
    from scripts.train_models import (
        train_travel_time_model,
        train_fuel_model,
        train_demand_model,
    )
    seed = args.seed if hasattr(args, "seed") and args.seed is not None else 42
    samples = args.samples if hasattr(args, "samples") and args.samples is not None else 50000
    output_dir = "results/models"

    if args.model == "travel_time":
        train_travel_time_model(samples=samples, seed=seed, output_dir=output_dir)
    elif args.model == "fuel":
        train_fuel_model(samples=samples, seed=seed, output_dir=output_dir)
    elif args.model == "demand":
        train_demand_model(samples=samples, seed=seed, output_dir=output_dir)
    elif args.model == "all":
        train_travel_time_model(samples=samples, seed=seed, output_dir=output_dir)
        train_fuel_model(samples=samples, seed=seed, output_dir=output_dir)
        train_demand_model(samples=samples, seed=seed, output_dir=output_dir)
    else:
        print(f"Unknown model '{args.model}'. Choose from: travel_time, fuel, demand, all")


def cli_simulate(args) -> None:
    """Run dynamic simulation scenario."""
    from scripts.run_simulation import run_simulation_scenario
    scenario = args.scenario or "full_disaster"
    dataset = args.dataset if hasattr(args, "dataset") and args.dataset else "C101"
    seed = args.seed if hasattr(args, "seed") and args.seed is not None else 42
    duration = args.duration if hasattr(args, "duration") and args.duration else 90.0
    run_simulation_scenario(scenario=scenario, dataset=dataset, seed=seed, duration_mins=duration)


def cli_run_experiment(args) -> None:
    """Run flagship disruption recovery experiment."""
    from scripts.run_experiment import run_experiment_cli
    dataset = args.dataset if hasattr(args, "dataset") and args.dataset else "C101"
    seed = args.seed if hasattr(args, "seed") and args.seed is not None else 42
    run_experiment_cli(dataset=dataset, seed=seed)


def main() -> None:
    common_parser = argparse.ArgumentParser(add_help=False)
    common_parser.add_argument(
        "--seed", type=int, default=42, help="Random seed for reproducibility"
    )

    parser = argparse.ArgumentParser(
        description="SWARMRoute: Autonomous AI Fleet Optimization Core",
        parents=[common_parser],
    )
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # download-data
    p_dl = subparsers.add_parser(
        "download-data", parents=[common_parser], help="Download benchmark datasets"
    )
    p_dl.add_argument("--instances", nargs="+", help="Specific Solomon instances to download")
    p_dl.add_argument("--force", action="store_true", help="Force re-download")

    # optimize
    p_opt = subparsers.add_parser(
        "optimize", parents=[common_parser], help="Run route optimization"
    )
    p_opt.add_argument("--dataset", default="C101", help="Solomon dataset name or path")
    p_opt.add_argument("--customers", type=int, default=None, help="Subset customer count (e.g. 25)")
    p_opt.add_argument("--vehicles", type=int, default=None, help="Number of vehicles in fleet")
    p_opt.add_argument("--time-limit", type=int, default=15, help="Solver time limit in seconds")
    p_opt.add_argument("--output", default=None, help="Path to save JSON results")

    # benchmark
    p_bm = subparsers.add_parser(
        "benchmark", parents=[common_parser], help="Run comparative benchmark"
    )
    p_bm.add_argument("--dataset", default="C101", help="Dataset name (e.g., C101, R101, RC101)")
    p_bm.add_argument("--customers", type=int, default=None, help="Subset customer count")
    p_bm.add_argument("--vehicles", type=int, default=None, help="Number of vehicles in fleet")
    p_bm.add_argument("--time-limit", type=int, default=15, help="Solver time limit in seconds")

    # train
    p_tr = subparsers.add_parser(
        "train", parents=[common_parser], help="Train predictive models"
    )
    p_tr.add_argument(
        "--model",
        choices=["travel_time", "fuel", "demand", "all"],
        default="travel_time",
        help="Which model to train",
    )
    p_tr.add_argument(
        "--samples",
        type=int,
        default=50000,
        help="Dataset size to train on (default: 50,000 for high accuracy)",
    )

    # preprocess
    subparsers.add_parser("preprocess", parents=[common_parser], help="Preprocess dynamic datasets")

    # simulate
    p_sim = subparsers.add_parser(
        "simulate", parents=[common_parser], help="Run dynamic fleet simulation"
    )
    p_sim.add_argument(
        "--scenario",
        choices=["normal", "traffic_spike", "truck_breakdown", "network_failure", "full_disaster"],
        default="full_disaster",
    )
    p_sim.add_argument("--dataset", default="C101", help="Solomon dataset name")
    p_sim.add_argument("--duration", type=float, default=90.0, help="Simulation duration in mins")

    # run-experiment
    p_exp = subparsers.add_parser(
        "run-experiment", parents=[common_parser], help="Run flagship recovery experiment"
    )
    p_exp.add_argument(
        "--scenario",
        choices=["disruption"],
        default="disruption",
        help="Experiment scenario to execute",
    )
    p_exp.add_argument("--dataset", default="C101", help="Solomon dataset name")

    # Placeholders for future phases to conform with CLI specs
    subparsers.add_parser("train-rl", parents=[common_parser], help="Train RL PPO fleet agent")
    subparsers.add_parser("evaluate", parents=[common_parser], help="Run comprehensive evaluation matrix")

    args = parser.parse_args()

    if args.command == "download-data":
        cli_download_data(args)
    elif args.command == "optimize":
        cli_optimize(args)
    elif args.command == "benchmark":
        cli_benchmark(args)
    elif args.command == "train":
        cli_train(args)
    elif args.command == "preprocess":
        cli_preprocess(args)
    elif args.command == "simulate":
        cli_simulate(args)
    elif args.command == "run-experiment":
        cli_run_experiment(args)
    elif args.command in ("train-rl", "evaluate"):
        print(f"Subcommand '{args.command}' scheduled for subsequent phases.")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
