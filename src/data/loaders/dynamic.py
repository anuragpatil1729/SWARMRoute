from __future__ import annotations
import csv
import json
import math
import random
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
from pydantic import BaseModel, Field

from src.models.order import Order, OrderStatus
from src.models.vehicle import Vehicle
from src.models.road import RoadNetwork
from src.models.fleet_state import FleetState, ConnectivityState
from src.data.loaders.solomon import load_solomon_benchmark


class TimePeriodOrders(BaseModel):
    """Orders released during a specific simulation or operational period."""
    period_index: int
    period_start_time: float
    period_end_time: float
    orders: List[Order] = Field(default_factory=list)


class DynamicMultiPeriodInstance(BaseModel):
    """
    Representation of a Dynamic Multi-Period Vehicle Routing Problem instance
    derived from Mendeley cbkzp5b8hb/1 and 5p5sv8hshj/1 benchmarks.
    """
    instance_name: str
    num_periods: int
    period_duration: float
    total_horizon: float
    depot_coordinates: Tuple[float, float]
    vehicle_capacity: float
    periods: List[TimePeriodOrders] = Field(default_factory=list)
    customer_demand_profiles: Dict[str, Dict[str, float]] = Field(default_factory=dict)


class DynamicOrderStream:
    """
    Generator/Stream of dynamic orders arriving throughout the simulation day.
    Simulates release times (T_release > 0), urgent requests, and variable customer demands.
    """

    def __init__(
        self,
        base_orders: List[Order],
        dynamic_ratio: float = 0.25,
        urgent_ratio: float = 0.10,
        max_horizon: float = 1200.0,
        seed: Optional[int] = 42,
    ) -> None:
        self.dynamic_ratio = dynamic_ratio
        self.urgent_ratio = urgent_ratio
        self.max_horizon = max_horizon
        self.rng = random.Random(seed)

        self.static_orders: List[Order] = []
        self.dynamic_orders: List[Order] = []
        self._partition_orders(base_orders)

    def _partition_orders(self, orders: List[Order]) -> None:
        for o in orders:
            is_dynamic = self.rng.random() < self.dynamic_ratio
            if is_dynamic:
                rel_time = round(self.rng.uniform(15.0, self.max_horizon * 0.65), 1)
                is_urgent = self.rng.random() < self.urgent_ratio
                priority = 5 if is_urgent else 2

                earliest = max(o.earliest_delivery, rel_time)
                latest = max(earliest + 60.0, o.latest_delivery)

                dyn_order = o.model_copy(
                    update={
                        "release_time": rel_time,
                        "earliest_delivery": earliest,
                        "latest_delivery": latest,
                        "priority": priority,
                        "status": OrderStatus.PENDING,
                    }
                )
                self.dynamic_orders.append(dyn_order)
            else:
                self.static_orders.append(o.model_copy(update={"release_time": 0.0}))

        self.dynamic_orders.sort(key=lambda x: x.release_time)

    def get_orders_released_between(self, start_time: float, end_time: float) -> List[Order]:
        return [o for o in self.dynamic_orders if start_time <= o.release_time < end_time]


class DynamicVRPDataLoader:
    """
    Complete loader and generator for Dynamic Multi-Period VRP datasets
    (Mendeley Data cbkzp5b8hb/1 & 5p5sv8hshj/1).
    """

    def __init__(
        self,
        raw_dir: Union[str, Path] = "data/raw/dynamic",
        processed_dir: Union[str, Path] = "data/processed",
        solomon_raw_dir: Union[str, Path] = "data/raw/solomon",
    ) -> None:
        self.raw_dir = Path(raw_dir)
        self.processed_dir = Path(processed_dir)
        self.solomon_raw_dir = Path(solomon_raw_dir)
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.processed_dir.mkdir(parents=True, exist_ok=True)

    def generate_and_save_raw_multiperiod_instance(
        self,
        base_instance: str = "C101",
        num_periods: int = 5,
        period_duration: float = 240.0,
        dynamic_ratio: float = 0.30,
        seed: int = 42,
    ) -> Path:
        """
        Synthesizes a concrete Dynamic Multi-Period instance conforming to the
        Mendeley Dynamic Multi-Period VRP structure and saves to data/raw/dynamic/.
        """
        fleet, net, meta = load_solomon_benchmark(
            base_instance, raw_dir=str(self.solomon_raw_dir)
        )
        base_orders = list(fleet.active_orders.values())
        depot_coord = meta["depot_coord"]
        total_horizon = num_periods * period_duration

        rng = random.Random(seed)

        # 1. Generate customer demand profiles
        customer_profiles: Dict[str, Dict[str, float]] = {}
        for o in base_orders:
            customer_profiles[o.order_id] = {
                "base_demand": o.demand_weight,
                "variance": round(rng.uniform(0.1, 0.4), 2),
                "order_frequency": round(rng.uniform(0.5, 1.0), 2),
                "urgency_probability": round(rng.uniform(0.05, 0.20), 2),
            }

        # 2. Partition into multi-period arrivals
        periods: List[TimePeriodOrders] = []
        for p in range(num_periods):
            p_start = p * period_duration
            p_end = (p + 1) * period_duration
            p_orders: List[Order] = []

            for o in base_orders:
                prof = customer_profiles[o.order_id]
                # Check if this customer places an order in period p
                if p == 0:
                    # Initial static orders
                    if rng.random() > dynamic_ratio:
                        p_orders.append(
                            o.model_copy(
                                update={
                                    "release_time": 0.0,
                                    "status": OrderStatus.PENDING,
                                }
                            )
                        )
                else:
                    # Dynamic orders arriving in period p
                    if rng.random() < prof["order_frequency"] * dynamic_ratio:
                        rel = round(rng.uniform(p_start, p_start + period_duration * 0.75), 1)
                        is_urgent = rng.random() < prof["urgency_probability"]
                        dem = max(
                            1.0,
                            round(prof["base_demand"] * rng.gauss(1.0, prof["variance"]), 1),
                        )
                        earliest = max(o.earliest_delivery, rel)
                        latest = max(earliest + 90.0, p_end)
                        p_orders.append(
                            Order(
                                order_id=f"{o.order_id}_P{p}",
                                pickup_location=depot_coord,
                                destination=o.destination,
                                demand_weight=dem,
                                volume=dem * 0.25,
                                priority=5 if is_urgent else 1,
                                earliest_delivery=earliest,
                                latest_delivery=latest,
                                service_time=o.service_time,
                                release_time=rel,
                                status=OrderStatus.PENDING,
                            )
                        )

            periods.append(
                TimePeriodOrders(
                    period_index=p,
                    period_start_time=p_start,
                    period_end_time=p_end,
                    orders=p_orders,
                )
            )

        multi_inst = DynamicMultiPeriodInstance(
            instance_name=f"Dynamic_{base_instance}_P{num_periods}",
            num_periods=num_periods,
            period_duration=period_duration,
            total_horizon=total_horizon,
            depot_coordinates=depot_coord,
            vehicle_capacity=meta["vehicle_capacity"],
            periods=periods,
            customer_demand_profiles=customer_profiles,
        )

        out_file = self.raw_dir / f"dynamic_{base_instance.lower()}_multiperiod.json"
        out_file.write_text(multi_inst.model_dump_json(indent=2), encoding="utf-8")

        # Also save CSV demand profiles for transparent analytics
        csv_file = self.raw_dir / "customer_demand_profiles.csv"
        with open(csv_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["order_id", "base_demand", "variance", "order_frequency", "urgency_probability"])
            for ord_id, vals in customer_profiles.items():
                writer.writerow([ord_id, vals["base_demand"], vals["variance"], vals["order_frequency"], vals["urgency_probability"]])

        return out_file

    def preprocess_dataset(self) -> List[Path]:
        """
        Preprocesses raw dynamic instances into validated deployment schedules in data/processed/.
        """
        processed_files: List[Path] = []
        for raw_path in self.raw_dir.glob("*.json"):
            content = json.loads(raw_path.read_text(encoding="utf-8"))
            inst = DynamicMultiPeriodInstance(**content)

            # Flatten all orders with period metadata
            all_orders = []
            for p in inst.periods:
                for o in p.orders:
                    all_orders.append(o.model_dump())

            summary = {
                "instance_name": inst.instance_name,
                "num_periods": inst.num_periods,
                "total_horizon": inst.total_horizon,
                "total_orders": len(all_orders),
                "orders_by_period": [len(p.orders) for p in inst.periods],
                "processed_orders": all_orders,
            }
            out_p = self.processed_dir / f"{inst.instance_name}_processed.json"
            out_p.write_text(json.dumps(summary, indent=2), encoding="utf-8")
            processed_files.append(out_p)

        return processed_files

    def load_processed_instance(self, instance_name: str) -> Optional[Dict[str, Any]]:
        candidate = self.processed_dir / f"{instance_name}_processed.json"
        if candidate.exists():
            return json.loads(candidate.read_text(encoding="utf-8"))
        return None
