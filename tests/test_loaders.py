import pytest
from pathlib import Path
from src.data.loaders.solomon import parse_solomon_file, load_solomon_benchmark
from src.data.loaders.dynamic import DynamicOrderStream
from src.models.order import Order


def test_parse_solomon_c101():
    solomon_path = Path("data/raw/solomon/C101.txt")
    if not solomon_path.exists():
        pytest.skip("Solomon C101.txt not found locally")

    parsed = parse_solomon_file(solomon_path)
    assert parsed.instance_name == "C101"
    assert parsed.capacity == 200.0
    assert parsed.depot_info["id"] == 0
    assert parsed.depot_info["x"] == 40.0
    assert parsed.depot_info["y"] == 50.0
    assert len(parsed.customers) == 100


def test_load_solomon_benchmark_subset():
    solomon_path = Path("data/raw/solomon/C101.txt")
    if not solomon_path.exists():
        pytest.skip("Solomon C101.txt not found locally")

    fleet, network, meta = load_solomon_benchmark("C101", max_customers=25, vehicle_count=5)
    assert meta["customer_count"] == 25
    assert len(fleet.active_orders) == 25
    assert len(fleet.vehicles) == 5
    assert network.graph.number_of_nodes() == 26  # 25 customers + 1 depot


def test_dynamic_order_stream_partitioning():
    dummy_orders = [
        Order(
            order_id=f"O_{i}",
            destination=(float(i), float(i)),
            demand_weight=10.0,
            earliest_delivery=0.0,
            latest_delivery=500.0,
        )
        for i in range(20)
    ]
    stream = DynamicOrderStream(dummy_orders, dynamic_ratio=0.30, seed=42)
    assert len(stream.static_orders) + len(stream.dynamic_orders) == 20
    assert len(stream.dynamic_orders) > 0
    # Dynamic orders must have positive release times
    for dyn_o in stream.dynamic_orders:
        assert dyn_o.release_time > 0.0
