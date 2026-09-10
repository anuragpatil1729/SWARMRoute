#!/usr/bin/env python3
"""
SWARMRoute: Autonomous AI Fleet Optimization Platform
Main CLI entry point.
"""
from __future__ import annotations
import argparse
import json
import os
import sys
import yaml
from pathlib import Path

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


def main() -> None:
    parser = argparse.ArgumentParser(
        description="SWARMRoute: Autonomous AI Fleet Optimization Core"
    )
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # download-data
    p_dl = subparsers.add_parser("download-data", help="Download benchmark datasets")
    p_dl.add_argument("--instances", nargs="+", help="Specific Solomon instances to download")
    p_dl.add_argument("--force", action="store_true", help="Force re-download")

    # optimize
    p_opt = subparsers.add_parser("optimize", help="Run route optimization")
    p_opt.add_argument("--dataset", default="C101", help="Solomon dataset name or path")
    p_opt.add_argument("--customers", type=int, default=None, help="Subset customer count (e.g. 25)")
    p_opt.add_argument("--vehicles", type=int, default=None, help="Number of vehicles in fleet")
    p_opt.add_argument("--time-limit", type=int, default=15, help="Solver time limit in seconds")
    p_opt.add_argument("--output", default=None, help="Path to save JSON results")

    # benchmark
    p_bm = subparsers.add_parser("benchmark", help="Run comparative benchmark")
    p_bm.add_argument("--dataset", default="C101", help="Dataset name (e.g., C101, R101, RC101)")
    p_bm.add_argument("--customers", type=int, default=None, help="Subset customer count")
    p_bm.add_argument("--vehicles", type=int, default=None, help="Number of vehicles in fleet")
    p_bm.add_argument("--time-limit", type=int, default=15, help="Solver time limit in seconds")

    # Placeholders for future phases to conform with CLI specs
    subparsers.add_parser("preprocess", help="Preprocess dynamic datasets")
    p_tr = subparsers.add_parser("train", help="Train predictive models")
    p_tr.add_argument("--model", choices=["travel_time", "fuel", "demand"])
    p_sim = subparsers.add_parser("simulate", help="Run dynamic fleet simulation")
    p_sim.add_argument("--scenario", choices=["normal", "traffic_spike", "truck_breakdown", "network_failure", "full_disaster"])
    subparsers.add_parser("train-rl", help="Train RL PPO fleet agent")
    subparsers.add_parser("evaluate", help="Run comprehensive evaluation matrix")

    args = parser.parse_args()

    if args.command == "download-data":
        cli_download_data(args)
    elif args.command == "optimize":
        cli_optimize(args)
    elif args.command == "benchmark":
        cli_benchmark(args)
    elif args.command in ("preprocess", "train", "simulate", "train-rl", "evaluate"):
        print(f"Subcommand '{args.command}' scheduled for subsequent phases.")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
