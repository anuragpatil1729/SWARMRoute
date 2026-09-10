# SWARMRoute: Autonomous AI Fleet Optimization Platform

Autonomous, resilient logistics fleet core designed to predict, optimize, redistribute loads, and recover from real-world disruptions (vehicle breakdowns, traffic congestion, road closures, and complete connectivity loss) using local edge intelligence and truck-to-truck mesh communication.

---

## Architecture Overview

The system strictly adheres to a three-layer decoupled architecture:

```
┌────────────────────────────────────────────────────────┐
│               Layer A — Prediction                     │
│  - Travel Time Predictor (Gradient Boosting / RF)      │
│  - Fuel Consumption Model (Physics & ML Hybrid)        │
│  - Customer Demand Predictor (Dynamic VRP distributions)│
└──────────────────────────┬─────────────────────────────┘
                           │
┌──────────────────────────▼─────────────────────────────┐
│           Layer B — Decision / Optimization             │
│  - LoadOptimizer (Weight/Volume/Cluster Bin Packing)    │
│  - RouteOptimizer & CVRPTW Solver (Google OR-Tools)    │
│  - DynamicReoptimizer (Local vs Global Self-Healing)   │
│  - DeliveryExchangeEngine (Autonomous Swapping)        │
│  - Multi-Agent Coordination (TruckAgent / FleetAgent)  │
└──────────────────────────┬─────────────────────────────┘
                           │
┌──────────────────────────▼─────────────────────────────┐
│              Layer C — Communication                   │
│  - Multi-hop Mesh Network Simulation                   │
│  - Topology Modes: CLOUD ↔ EDGE ↔ MESH ↔ DISCONNECTED   │
│  - Disconnected Operations & Event Synchronization     │
└────────────────────────────────────────────────────────┘
```

---

## Directory Structure

```
SWARMRoute/
├── configs/
│   └── config.yaml             # Multi-objective weights & system parameters
├── data/
│   ├── raw/
│   │   ├── solomon/            # C101, R101, RC101 VRPTW benchmark instances
│   │   └── dynamic/            # Dynamic Multi-Period VRP dataset scaffolding
│   ├── processed/              # Processed dynamic scenarios
│   └── external/
├── src/
│   ├── models/                 # Pydantic core models: Order, Vehicle, Road, FleetState
│   ├── data/loaders/           # Solomon and dynamic dataset parsers
│   ├── optimization/           # OR-Tools CVRPTW, LoadOptimizer, RouteOptimizer
│   ├── prediction/             # FuelModel (Physics-based & extensible ML)
│   ├── simulation/             # Traffic, events, and fleet simulation
│   ├── networking/             # Mesh network and connectivity modes
│   ├── agents/                 # Autonomous truck agents
│   └── evaluation/             # Standard metrics and benchmark comparisons
├── scripts/
│   └── download_datasets.py    # Automated dataset retriever
├── tests/                      # Automated unit and integration test suite
├── results/                    # Experiment runs, metrics, plots, and logs
├── requirements.txt
├── main.py                     # Unified CLI entrypoint
└── README.md
```

---

## Quickstart

### 1. Installation
```bash
pip install -r requirements.txt
```

### 2. Download Datasets
Download Solomon benchmark instances (C101, R101, RC101):
```bash
python main.py download-data
```

### 3. Run Route Optimization
Solve CVRPTW on Solomon C101 with OR-Tools:
```bash
# 25 customers
python main.py optimize --dataset C101 --customers 25

# Full 100 customers
python main.py optimize --dataset C101 --time-limit 10
```

### 4. Run Benchmark Comparison
Benchmark the OR-Tools optimizer against conventional heuristics (Nearest-Neighbor):
```bash
python main.py benchmark --dataset C101
```

Benchmark Output (measured with leg-by-leg payload tracking):
```
====================================================
AUTONOMOUS FLEET OPTIMIZATION BENCHMARK
Dataset: Solomon C101
Vehicles: 10
Orders: 100
====================================================
BASELINE (Heuristic)
Distance: 1,311.5 km
Fuel: 475.9 L
CO2: 1,275.5 kg
Late deliveries: 59
Cost: ₹381,053.98
Runtime: 0.00 sec
----------------------------------------------------
AI/DYNAMIC SYSTEM (OR-Tools)
Distance: 828.9 km
Fuel: 314.9 L
CO2: 844.0 kg
Late deliveries: 0
Cost: ₹4,040.64
Recovery time: 15.01 sec
----------------------------------------------------
IMPROVEMENT
Fuel reduction: 33.8 %
CO2 reduction: 33.8 %
Cost reduction: 98.9 %
Late deliveries: 100.0 %
====================================================
```

### 5. Train Prediction Models (Layer A)
Train travel time, fuel consumption, and customer demand models:
```bash
python main.py train --model all --samples 50000 --seed 42
```
All models achieve $R^2 > 0.97$ and are saved to `results/models/`.

### 6. Preprocess Dynamic Multi-Period Datasets
Generate and partition dynamic period scenarios:
```bash
python main.py preprocess
```

### 7. Run Fleet & Traffic Simulation
Simulate fleet operations under dynamic traffic, accidents, and breakdowns:
```bash
python main.py simulate --scenario full_disaster --duration 90
```

### 8. Run Flagship Recovery Experiment
Evaluate fleet resilience during a catastrophic simultaneous event (**Internet Blackout + Truck Breakdown + Traffic Spike**):
```bash
python main.py run-experiment --scenario disruption
```

Flagship Experiment Results:
```
================================================================================
 FLAGSHIP EXPERIMENT: DISRUPTION RECOVERY UNDER INTERNET BLACKOUT
 Scenario: Internet OFF + Truck Breakdown + Traffic Spike + Urgent Orders
 Dataset: Solomon C101 | Random Seed: 42
================================================================================
METRIC                           | CONVENTIONAL (Centralized) | SWARMRoute (Resilient)
--------------------------------------------------------------------------------
Connectivity Mode                | OFFLINE (Failed uplink)  | MESH_MODE (Multi-hop) 
Mesh Relay Hops                  | None (No ad-hoc radio)   | 1 hops (20.0 ms)      
Completed Deliveries             | 91 / 108                 | 108 / 108             
Completion Rate                  | 84.3 %                   | 100.0 %               
Failed / Abandoned Orders        | 17 orders                | 0 orders              
Late Deliveries                  | 28 late                  | 1 late                
Recovery Time                    | Failed (Infinite)        | 0.001 sec             
Total Fuel Consumed              | 362.1 L                  | 301.3 L               
Total CO2 Emissions              | 970.6 kg                 | 807.5 kg              
--------------------------------------------------------------------------------
```

### 9. Run Automated Tests
```bash
pytest -v
```
All 26 unit and integration tests validate capacity bounds, time windows, lateness accounting, fuel/CO₂ physics, mesh routing, dynamic reoptimization, and dataset loaders.
