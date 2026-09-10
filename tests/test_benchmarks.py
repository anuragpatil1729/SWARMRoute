import pytest
from pathlib import Path
from src.data.loaders.solomon import load_solomon_benchmark
from src.evaluation.benchmarks import run_benchmark_comparison


def test_benchmark_comparison():
    solomon_path = Path("data/raw/solomon/C101.txt")
    if not solomon_path.exists():
        pytest.skip("Solomon C101.txt not found locally")

    fleet, network, meta = load_solomon_benchmark("C101", max_customers=25, vehicle_count=10)
    baseline_metrics, opt_metrics, improvements = run_benchmark_comparison(
        fleet_state=fleet,
        road_network=network,
        dataset_name="Solomon C101 (25)",
        time_limit_sec=5,
    )

    assert baseline_metrics.total_distance_km > 0
    assert opt_metrics.total_distance_km > 0
    # OR-Tools baseline should outperform heuristic on distance/fuel
    assert opt_metrics.total_distance_km <= baseline_metrics.total_distance_km
    assert opt_metrics.late_deliveries <= baseline_metrics.late_deliveries
    assert improvements["fuel_reduction_pct"] >= 0.0
    assert improvements["cost_reduction_pct"] >= 0.0
