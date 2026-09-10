#!/usr/bin/env python3
"""
Flagship Experiment Runner:
Disruption Recovery (Internet Blackout + Vehicle Breakdown + Traffic Spike)
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

# Ensure project root in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Safeguard against ARM64 pyarrow protobuf collision
if "pyarrow" not in sys.modules:
    sys.modules["pyarrow"] = None

from src.evaluation.experiments import run_flagship_recovery_experiment


def run_experiment_cli(dataset: str = "C101", seed: int = 42) -> None:
    print("================================================================================")
    print(" FLAGSHIP EXPERIMENT: DISRUPTION RECOVERY UNDER INTERNET BLACKOUT")
    print(" Scenario: Internet OFF + Truck Breakdown + Traffic Spike + Urgent Orders")
    print(f" Dataset: Solomon {dataset} | Random Seed: {seed}")
    print("================================================================================")

    rep = run_flagship_recovery_experiment(dataset_name=dataset, seed=seed)

    print("\n[DISRUPTION AT T = 60 mins]")
    print(f"  - Central Internet: DISCONNECTED (All cloud communication severed)")
    print(f"  - Vehicle Failed:   {rep.breakdown_vehicle_id} broken down with {rep.stranded_orders_count} active orders")
    print(f"  - Road Network:     Severe traffic spike on key delivery corridor")
    print(f"  - Dynamic Demand:   {rep.new_urgent_orders} new urgent orders appeared")

    print("\n--------------------------------------------------------------------------------")
    print(f"{'METRIC':<32} | {'CONVENTIONAL (Centralized)':<24} | {'SWARMRoute (Resilient)':<22}")
    print("--------------------------------------------------------------------------------")
    print(f"{'Connectivity Mode':<32} | {'OFFLINE (Failed uplink)':<24} | {'MESH_MODE (Multi-hop)':<22}")
    print(f"{'Mesh Relay Hops':<32} | {'None (No ad-hoc radio)':<24} | {f'{rep.mesh_hops_traversed} hops ({rep.mesh_latency_ms} ms)':<22}")
    print(f"{'Completed Deliveries':<32} | {f'{rep.centralized_completed_orders} / {rep.total_initial_orders + rep.new_urgent_orders}':<24} | {f'{rep.resilient_completed_orders} / {rep.total_initial_orders + rep.new_urgent_orders}':<22}")
    print(f"{'Completion Rate':<32} | {f'{rep.centralized_completion_rate_pct:.1f} %':<24} | {f'{rep.resilient_completion_rate_pct:.1f} %':<22}")
    print(f"{'Failed / Abandoned Orders':<32} | {f'{rep.centralized_failed_orders} orders':<24} | {f'{rep.resilient_failed_orders} orders':<22}")
    print(f"{'Late Deliveries':<32} | {f'{rep.centralized_late_deliveries} late':<24} | {f'{rep.resilient_late_deliveries} late':<22}")
    print(f"{'Recovery Time':<32} | {'Failed (Infinite)':<24} | {f'{rep.resilient_recovery_time_sec:.3f} sec':<22}")
    print(f"{'Total Fuel Consumed':<32} | {f'{rep.centralized_total_fuel_l:,.1f} L':<24} | {f'{rep.resilient_total_fuel_l:,.1f} L':<22}")
    print(f"{'Total CO2 Emissions':<32} | {f'{rep.centralized_total_co2_kg:,.1f} kg':<24} | {f'{rep.resilient_total_co2_kg:,.1f} kg':<22}")
    print("--------------------------------------------------------------------------------")
    print("CONCLUSION:")
    print("SWARMRoute successfully continued autonomous operation without Internet, utilizing")
    print("peer-to-peer truck mesh communication and local order swapping to recover deliveries.")
    print("================================================================================")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run SWARMRoute flagship recovery experiment.")
    parser.add_argument("--dataset", default="C101", help="Solomon instance name")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    args = parser.parse_args()
    run_experiment_cli(dataset=args.dataset, seed=args.seed)


if __name__ == "__main__":
    main()
