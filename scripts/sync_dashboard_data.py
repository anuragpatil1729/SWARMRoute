#!/usr/bin/env python3
"""
SWARMRoute: Dashboard Data Synchronization Utility
Synchronizes empirical simulation and benchmark outputs from results/
into the Next.js dashboard data repository (swarmroute-dashboard/lib/data/).
"""
import json
import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DASHBOARD_DATA_DIR = PROJECT_ROOT / "dashboard" / "lib" / "data"

SYNC_MAPPINGS = [
    {
        "source": PROJECT_ROOT / "results" / "benchmarks" / "final_comparison.json",
        "target": DASHBOARD_DATA_DIR / "finalComparison.json",
        "name": "Multi-seed Benchmark Comparison",
    },
    {
        "source": PROJECT_ROOT / "results" / "experiments" / "ppo_ablation.json",
        "target": DASHBOARD_DATA_DIR / "ppoAblation.json",
        "name": "PPO Predictor Ablation Study",
    },
    {
        "source": PROJECT_ROOT / "results" / "logs" / "ppo_training_metrics.json",
        "target": DASHBOARD_DATA_DIR / "ppoTraining.json",
        "name": "PPO Training & Episode Metrics",
    },
    {
        "source": (
            PROJECT_ROOT / "results" / "experiments" / "disruption_scenarios.json"
            if (PROJECT_ROOT / "results" / "experiments" / "disruption_scenarios.json").exists()
            else PROJECT_ROOT / "results" / "disruptions" / "disruption_scenarios.json"
        ),
        "target": DASHBOARD_DATA_DIR / "disruptionScenarios.json",
        "name": "Disruption Scenarios (A-H)",
    },
]


def sync_dashboard_data() -> None:
    print("================================================================================")
    print("          SWARMRoute: Syncing Benchmark & Simulation Data to Dashboard          ")
    print("================================================================================")
    DASHBOARD_DATA_DIR.mkdir(parents=True, exist_ok=True)

    synced_count = 0
    for item in SYNC_MAPPINGS:
        src = item["source"]
        tgt = item["target"]
        name = item["name"]

        if src.exists():
            shutil.copy2(src, tgt)
            size_kb = tgt.stat().st_size / 1024.0
            print(f"[SYNCED]  {name:35s} -> {tgt.name} ({size_kb:.1f} KB)")
            synced_count += 1
        else:
            if tgt.exists():
                size_kb = tgt.stat().st_size / 1024.0
                print(f"[RETAIN]  {name:35s} (Using existing dashboard checkpoint: {size_kb:.1f} KB)")
            else:
                print(f"[MISSING] {name:35s} (Source not found: {src.relative_to(PROJECT_ROOT)})")

    print(f"\nCompleted data sync: {synced_count} file(s) updated in {DASHBOARD_DATA_DIR.relative_to(PROJECT_ROOT)}.")
    print("================================================================================\n")


if __name__ == "__main__":
    sync_dashboard_data()
