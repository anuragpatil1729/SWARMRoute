import pytest
from src.evaluation.experiments import run_flagship_recovery_experiment


def test_flagship_recovery_experiment():
    rep = run_flagship_recovery_experiment(dataset_name="C101", seed=42)

    assert rep.total_initial_orders == 100
    assert rep.new_urgent_orders == 8
    assert rep.stranded_orders_count > 0

    # Resilient system should beat centralized during blackout
    assert rep.resilient_completion_rate_pct > rep.centralized_completion_rate_pct
    assert rep.resilient_completed_orders > rep.centralized_completed_orders
    assert rep.resilient_failed_orders < rep.centralized_failed_orders
    assert rep.resilient_failed_orders == 0

    # Mesh metrics
    assert rep.mesh_delivery_success is True
    assert rep.mesh_hops_traversed >= 1
    assert rep.mesh_latency_ms >= 20.0
