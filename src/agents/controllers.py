from __future__ import annotations
import copy
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple

from src.models.fleet_state import FleetState, ConnectivityState
from src.models.road import RoadNetwork
from src.models.vehicle import Vehicle, VehicleStatus
from src.simulation.environment import FleetSimulationEnvironment
from src.agents.centralized_agent import CentralizedAgent
from src.agents.fleet_agent import FleetAgent
from src.networking.mesh import MeshNetwork


class BaseFleetController(ABC):
    """
    Standard interface for fleet controllers.
    Ensures identical environment interaction and identical initial conditions.
    """
    def __init__(self, name: str) -> None:
        self.name = name

    @abstractmethod
    def on_disruption(
        self,
        env: FleetSimulationEnvironment,
        disruption_event: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Handles dynamic disruptions during simulation execution."""
        pass


class CentralizedController(BaseFleetController):
    """
    Conventional Centralized Fleet Controller.
    Assumes global fleet state, global order state, and global traffic state are available.
    Requires cloud/Internet connection to coordinate trucks.
    During cloud outage / disconnection, cannot communicate with trucks or issue re-routes.
    """
    def __init__(self) -> None:
        super().__init__(name="Centralized")
        self.agent = CentralizedAgent()

    def on_disruption(
        self,
        env: FleetSimulationEnvironment,
        disruption_event: Dict[str, Any],
    ) -> Dict[str, Any]:
        start_t = time.perf_counter()
        breakdown_id = disruption_event.get("vehicle_id")

        # Check cloud connectivity
        if env.fleet_state.connectivity_state != ConnectivityState.CLOUD_MODE:
            # Cloud severed: central dispatcher cannot reach trucks
            return {
                "success": False,
                "recovery_time_sec": time.perf_counter() - start_t,
                "reason": "Cloud disconnected; unable to command edge vehicles",
            }

        if breakdown_id:
            res = self.agent.handle_breakdown(
                fleet_state=env.fleet_state,
                road_network=env.road_network,
                broken_vehicle_id=breakdown_id,
                current_time_mins=env.current_time_mins,
            )
            rec_time = time.perf_counter() - start_t
            env.recovery_time_sec = rec_time
            return {
                "success": res is not None and res.status in ("OPTIMAL", "FEASIBLE"),
                "recovery_time_sec": rec_time,
                "optimization_result": res,
            }

        return {"success": False, "recovery_time_sec": 0.0}


class SWARMRouteController(BaseFleetController):
    """
    SWARMRoute Decentralized Peer-to-Peer Controller.
    Relies strictly on local truck edge agents and ad-hoc wireless mesh communication.
    Operates without Internet or cloud dependency during outages.
    Uses decentralized bidding and delivery exchange.
    """
    def __init__(self, fleet_agent: FleetAgent) -> None:
        super().__init__(name="SWARMRoute")
        self.fleet_agent = fleet_agent

    def on_disruption(
        self,
        env: FleetSimulationEnvironment,
        disruption_event: Dict[str, Any],
    ) -> Dict[str, Any]:
        start_t = time.perf_counter()
        breakdown_id = disruption_event.get("vehicle_id")

        if breakdown_id:
            # Executes decentralized multi-hop recovery over mesh
            recovery_info = self.fleet_agent.on_vehicle_breakdown_decentralized(
                failed_vehicle_id=breakdown_id,
                current_time_mins=env.current_time_mins,
                node_id_map=env.node_id_map,
            )
            rec_time = time.perf_counter() - start_t
            env.recovery_time_sec = rec_time

            if recovery_info.get("success"):
                env.execute_action({
                    "type": "REASSIGN_ORDERS",
                    "transfers": recovery_info.get("transfers", []),
                })

            recovery_info["recovery_time_sec"] = rec_time
            return recovery_info

        return {"success": False, "recovery_time_sec": 0.0}
