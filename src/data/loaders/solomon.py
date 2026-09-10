from __future__ import annotations
import math
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from src.models.order import Order, OrderStatus
from src.models.vehicle import Vehicle, VehicleStatus
from src.models.road import RoadNetwork, TrafficLevel
from src.models.fleet_state import FleetState, ConnectivityState


class SolomonInstanceData:
    """Raw parsed data from a Solomon VRPTW benchmark file."""

    def __init__(self) -> None:
        self.instance_name: str = ""
        self.max_vehicles: int = 0
        self.capacity: float = 0.0
        self.depot_info: Dict[str, Any] = {}
        self.customers: List[Dict[str, Any]] = []


def parse_solomon_file(file_path: Union[str, Path]) -> SolomonInstanceData:
    """
    Parses a Solomon VRPTW instance file according to standard format:
    Instance name -> VEHICLE block -> CUSTOMER block.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Solomon instance file not found at: {path}")

    data = SolomonInstanceData()
    lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines()]

    section = "HEADER"
    for line in lines:
        if not line:
            continue

        if line.startswith("VEHICLE"):
            section = "VEHICLE_HEADER"
            continue
        elif line.startswith("CUSTOMER"):
            section = "CUSTOMER_HEADER"
            continue

        if section == "HEADER" and not data.instance_name:
            data.instance_name = line
        elif section == "VEHICLE_HEADER":
            if "NUMBER" in line:
                continue
            parts = line.split()
            if len(parts) >= 2 and parts[0].isdigit():
                data.max_vehicles = int(parts[0])
                data.capacity = float(parts[1])
                section = "WAIT_CUSTOMER"
        elif section in ("CUSTOMER_HEADER", "WAIT_CUSTOMER"):
            if "CUST NO." in line:
                section = "CUSTOMERS"
                continue
            # Sometimes header is on previous line
            parts = line.split()
            if len(parts) >= 7 and parts[0].isdigit():
                section = "CUSTOMERS"
                # fall through to parse customer row
        if section == "CUSTOMERS":
            parts = line.split()
            if len(parts) >= 7 and parts[0].isdigit():
                cust_id = int(parts[0])
                x = float(parts[1])
                y = float(parts[2])
                demand = float(parts[3])
                ready_time = float(parts[4])
                due_date = float(parts[5])
                service_time = float(parts[6])

                record = {
                    "id": cust_id,
                    "x": x,
                    "y": y,
                    "demand": demand,
                    "ready_time": ready_time,
                    "due_date": due_date,
                    "service_time": service_time,
                }

                if cust_id == 0:
                    data.depot_info = record
                else:
                    data.customers.append(record)

    if not data.depot_info:
        raise ValueError(f"No depot (cust_no 0) found in {file_path}")

    return data


def load_solomon_benchmark(
    dataset_name_or_path: Union[str, Path],
    max_customers: Optional[int] = None,
    vehicle_count: Optional[int] = None,
    raw_dir: str = "data/raw/solomon",
) -> Tuple[FleetState, RoadNetwork, Dict[str, Any]]:
    """
    High-level loader transforming a Solomon benchmark file into:
      - FleetState (vehicles, active_orders, connectivity)
      - RoadNetwork (graph nodes, coordinates, distance metrics)
      - Metadata dictionary
    """
    path = Path(dataset_name_or_path)
    if not path.exists():
        # Check standard raw_dir location
        candidate = Path(raw_dir) / f"{dataset_name_or_path}.txt"
        if candidate.exists():
            path = candidate
        else:
            candidate_lower = Path(raw_dir) / f"{str(dataset_name_or_path).lower()}.txt"
            if candidate_lower.exists():
                path = candidate_lower
            else:
                raise FileNotFoundError(
                    f"Cannot locate benchmark instance '{dataset_name_or_path}'. Tried {path} and {candidate}."
                )

    parsed = parse_solomon_file(path)
    customers = parsed.customers
    if max_customers is not None and max_customers > 0:
        customers = customers[:max_customers]

    depot = parsed.depot_info
    depot_coord = (depot["x"], depot["y"])

    # 1. Construct RoadNetwork
    network = RoadNetwork(name=f"Solomon_{parsed.instance_name}")
    # Add depot as node 0
    network.add_node(
        node_id=0,
        x=depot["x"],
        y=depot["y"],
        is_depot=True,
        ready_time=depot["ready_time"],
        due_date=depot["due_date"],
    )

    # Add customer nodes
    for c in customers:
        network.add_node(
            node_id=c["id"],
            x=c["x"],
            y=c["y"],
            is_depot=False,
            demand=c["demand"],
            ready_time=c["ready_time"],
            due_date=c["due_date"],
            service_time=c["service_time"],
        )

    # 2. Construct Orders
    orders: Dict[str, Order] = {}
    for c in customers:
        order_id = f"ORD_{c['id']:03d}"
        order = Order(
            order_id=order_id,
            pickup_location=depot_coord,
            destination=(c["x"], c["y"]),
            demand_weight=c["demand"],
            volume=c["demand"] * 0.25,  # Approx volume conversion
            priority=1,
            earliest_delivery=c["ready_time"],
            latest_delivery=c["due_date"],
            service_time=c["service_time"],
            release_time=0.0,
            status=OrderStatus.PENDING,
        )
        orders[order_id] = order

    # 3. Construct Vehicles
    num_vehicles = vehicle_count if vehicle_count is not None else parsed.max_vehicles
    vehicles: Dict[str, Vehicle] = {}
    for i in range(1, num_vehicles + 1):
        veh_id = f"TRUCK_{i:02d}"
        vehicle = Vehicle(
            vehicle_id=veh_id,
            vehicle_type="heavy_duty",
            max_weight=parsed.capacity,
            max_volume=parsed.capacity * 0.35,
            current_location=depot_coord,
            current_load=0.0,
            fuel_level=300.0,
            fuel_capacity=300.0,
            fuel_efficiency=30.0,
            average_speed=40.0,
            status=VehicleStatus.IDLE,
            current_route=[],
            assigned_orders=[],
        )
        vehicles[veh_id] = vehicle

    # 4. Construct Initial FleetState
    fleet_state = FleetState(
        timestamp=0.0,
        vehicles=vehicles,
        active_orders=orders,
        road_network=network,
        traffic_state={},
        connectivity_state=ConnectivityState.CLOUD_MODE,
    )

    metadata = {
        "instance_name": parsed.instance_name,
        "customer_count": len(customers),
        "vehicle_count": len(vehicles),
        "vehicle_capacity": parsed.capacity,
        "depot_coord": depot_coord,
        "depot_due_date": depot["due_date"],
        "node_ids": [0] + [c["id"] for c in customers],
    }

    return fleet_state, network, metadata
