from __future__ import annotations
import json
import random
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from src.models.order import Order, OrderStatus
from src.models.road import RoadNetwork
from src.models.fleet_state import FleetState


class DynamicOrderStream:
    """
    Generator/Stream of dynamic orders arriving throughout the simulation day.
    Simulates release times (T_release > 0), urgent requests, and variable customer demands
    based on dynamic routing datasets (e.g. Mendeley Dynamic VRP / dynamic Solomon).
    """

    def __init__(
        self,
        base_orders: List[Order],
        dynamic_ratio: float = 0.20,
        urgent_ratio: float = 0.05,
        max_horizon: float = 1000.0,
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
                # Assign a dynamic release time within the first 60% of time horizon
                rel_time = round(self.rng.uniform(10.0, self.max_horizon * 0.6), 1)
                is_urgent = self.rng.random() < self.urgent_ratio
                priority = 5 if is_urgent else 1

                # Adjust time windows to ensure valid window after release
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

        # Sort dynamic orders by release time
        self.dynamic_orders.sort(key=lambda x: x.release_time)

    def get_orders_released_at(self, current_time: float) -> List[Order]:
        """Returns orders released up to current_time that were not released previously."""
        return [o for o in self.dynamic_orders if o.release_time <= current_time]


class DynamicVRPDataLoader:
    """
    Loader for the Dynamic Multi-Period VRP dataset (Mendeley cbkzp5b8hb/1 & 5p5sv8hshj/1).
    Reads processed files or generates dynamic instance streams from raw benchmarks.
    """

    def __init__(
        self,
        raw_dir: Union[str, Path] = "data/raw/dynamic",
        processed_dir: Union[str, Path] = "data/processed",
    ) -> None:
        self.raw_dir = Path(raw_dir)
        self.processed_dir = Path(processed_dir)
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.processed_dir.mkdir(parents=True, exist_ok=True)

    def save_dynamic_instance(
        self,
        name: str,
        static_orders: List[Order],
        dynamic_orders: List[Order],
        metadata: Dict[str, Any],
    ) -> Path:
        """Saves processed dynamic instance into JSON format."""
        out_path = self.processed_dir / f"{name}_dynamic.json"
        payload = {
            "name": name,
            "metadata": metadata,
            "static_orders": [o.model_dump() for o in static_orders],
            "dynamic_orders": [o.model_dump() for o in dynamic_orders],
        }
        out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return out_path

    def load_dynamic_instance(
        self, name: str
    ) -> Optional[Tuple[List[Order], List[Order], Dict[str, Any]]]:
        """Loads a processed dynamic instance from disk if available."""
        file_path = self.processed_dir / f"{name}_dynamic.json"
        if not file_path.exists():
            return None
        payload = json.loads(file_path.read_text(encoding="utf-8"))
        static_orders = [Order(**d) for d in payload["static_orders"]]
        dynamic_orders = [Order(**d) for d in payload["dynamic_orders"]]
        return static_orders, dynamic_orders, payload.get("metadata", {})
