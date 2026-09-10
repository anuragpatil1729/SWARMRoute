import pytest
from src.prediction.fuel import DeterministicFuelModel
from src.models.road import TrafficLevel


def test_fuel_consumption_load_effect():
    model = DeterministicFuelModel()
    dist = 100.0  # km

    fuel_empty = model.calculate_fuel(
        vehicle_type="heavy_duty",
        vehicle_load=0.0,
        max_weight=200.0,
        distance=dist,
    )
    fuel_loaded = model.calculate_fuel(
        vehicle_type="heavy_duty",
        vehicle_load=200.0,
        max_weight=200.0,
        distance=dist,
    )

    assert fuel_loaded > fuel_empty
    # With 40% payload penalty, full load should consume ~40% more fuel
    assert pytest.approx(fuel_loaded / fuel_empty, rel=0.05) == 1.40


def test_fuel_consumption_traffic_effect():
    model = DeterministicFuelModel()
    dist = 50.0

    fuel_normal = model.calculate_fuel(
        vehicle_type="heavy_duty",
        vehicle_load=100.0,
        max_weight=200.0,
        distance=dist,
        traffic_level=TrafficLevel.NORMAL,
    )
    fuel_heavy = model.calculate_fuel(
        vehicle_type="heavy_duty",
        vehicle_load=100.0,
        max_weight=200.0,
        distance=dist,
        traffic_level=TrafficLevel.HEAVY,
    )

    assert fuel_heavy > fuel_normal


def test_fuel_consumption_gradient_effect():
    model = DeterministicFuelModel()
    dist = 50.0

    fuel_flat = model.calculate_fuel(
        vehicle_type="heavy_duty",
        vehicle_load=100.0,
        max_weight=200.0,
        distance=dist,
        road_gradient=0.0,
    )
    fuel_uphill = model.calculate_fuel(
        vehicle_type="heavy_duty",
        vehicle_load=100.0,
        max_weight=200.0,
        distance=dist,
        road_gradient=5.0,  # +5% steep hill
    )

    assert fuel_uphill > fuel_flat


def test_co2_calculation():
    model = DeterministicFuelModel()
    fuel_liters = 50.0
    co2 = model.calculate_co2(fuel_liters, fuel_type="diesel")
    # 50L * 2.68 kg/L = 134.0 kg CO2
    assert pytest.approx(co2, rel=1e-3) == 134.0
