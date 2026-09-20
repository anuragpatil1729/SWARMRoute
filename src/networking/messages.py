from __future__ import annotations
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class MessageType(str, Enum):
    FLEET_STATE_UPDATE = "FLEET_STATE_UPDATE"
    BREAKDOWN_ALERT = "BREAKDOWN_ALERT"
    SOS_BREAKDOWN = "BREAKDOWN_ALERT"  # Backward-compatible alias
    ORDER_TRANSFER_REQUEST = "ORDER_TRANSFER_REQUEST"
    ORDER_TRANSFER_ACCEPT = "ORDER_TRANSFER_ACCEPT"
    ORDER_TRANSFER_REJECT = "ORDER_TRANSFER_REJECT"
    ROUTE_UPDATE = "ROUTE_UPDATE"
    TRAFFIC_ALERT = "TRAFFIC_ALERT"
    ROAD_CLOSURE_ALERT = "ROAD_CLOSURE_ALERT"
    EMERGENCY_ORDER = "EMERGENCY_ORDER"
    CONNECTIVITY_STATUS = "CONNECTIVITY_STATUS"
    STATE_SYNC = "STATE_SYNC"
    HEARTBEAT = "HEARTBEAT"
    CHAT_MESSAGE = "CHAT_MESSAGE"


class MeshMessage(BaseModel):
    """
    Standard packet transmitted over the simulated truck-to-truck mesh network.
    """
    message_id: str
    message_type: MessageType
    sender_id: str
    receiver_id: str = "BROADCAST"  # "BROADCAST" or specific vehicle ID
    timestamp_mins: float
    payload: Dict[str, Any] = Field(default_factory=dict)
    hop_count: int = 0
    route_taken: List[str] = Field(default_factory=list)
    total_latency_ms: float = 0.0
    delivered: bool = False
