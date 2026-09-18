"""
Temporal Trajectory Transformer for SWARMRoute Route Intelligence.
Processes rolling GPS and vehicle state sequences (T-5 to T0) using
multi-head self-attention to encode dynamic operational trends
(acceleration/deceleration trends, fuel drain rate, traffic friction accumulation,
and schedule slip).
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

try:
    import torch
    import torch.nn as nn
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    torch = None  # type: ignore
    nn = object  # type: ignore


class TrajectoryTemporalTransformer(nn.Module if TORCH_AVAILABLE else object):
    """
    Self-attention encoder over temporal sequences of vehicle state vectors.
    Inputs: [Batch, Sequence_Len=6, Feature_Dim=12]
    Output: [Batch, Hidden_Dim=64] trajectory embedding
    """

    FEATURE_NAMES = [
        "lat_norm",
        "lon_norm",
        "speed_norm",
        "heading_norm",
        "fuel_norm",
        "traffic_norm",
        "road_friction",
        "eta_mins_norm",
        "route_progress",
        "urgency_norm",
        "connectivity_code",
        "vehicle_condition_norm",
    ]

    INPUT_DIM = 12
    SEQ_LEN = 6  # T-5, T-4, T-3, T-2, T-1, T0
    HIDDEN_DIM = 64
    NUM_HEADS = 4
    NUM_LAYERS = 2

    def __init__(self, hidden_dim: int = 64, num_heads: int = 4, num_layers: int = 2) -> None:
        if not TORCH_AVAILABLE:
            return
        super().__init__()
        self.hidden_dim = hidden_dim
        self.input_projection = nn.Linear(self.INPUT_DIM, hidden_dim)
        self.pos_embedding = nn.Parameter(torch.zeros(1, self.SEQ_LEN, hidden_dim))
        
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=hidden_dim,
            nhead=num_heads,
            dim_feedforward=hidden_dim * 2,
            dropout=0.1,
            activation="relu",
            batch_first=True,
        )
        self.transformer_encoder = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)
        
        # Summary heads for derived trajectory metrics
        self.pooling = nn.AdaptiveAvgPool1d(1)
        self.trend_head = nn.Sequential(
            nn.Linear(hidden_dim, 32),
            nn.ReLU(),
            nn.Linear(32, 4),  # [speed_trend, fuel_drain_trend, delay_risk, reroute_desirability]
        )
        self._init_weights()

    def _init_weights(self) -> None:
        if not TORCH_AVAILABLE:
            return
        nn.init.normal_(self.pos_embedding, std=0.02)
        for p in self.parameters():
            if p.dim() > 1 and p is not self.pos_embedding:
                nn.init.xavier_uniform_(p)

    def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        x: Tensor of shape [Batch, SEQ_LEN, INPUT_DIM]
        returns: (embedding [Batch, HIDDEN_DIM], trend_metrics [Batch, 4])
        """
        if not TORCH_AVAILABLE:
            raise RuntimeError("PyTorch is not available.")
        
        b, s, f = x.size()
        proj = self.input_projection(x) + self.pos_embedding[:, :s, :]
        encoded = self.transformer_encoder(proj)  # [Batch, SEQ_LEN, HIDDEN_DIM]
        
        # Pool across sequence dimension (temporal aggregation)
        pooled = encoded.transpose(1, 2)  # [Batch, HIDDEN_DIM, SEQ_LEN]
        rep = self.pooling(pooled).squeeze(-1)  # [Batch, HIDDEN_DIM]
        
        trends = self.trend_head(rep)  # [Batch, 4]
        return rep, trends


class TemporalTransformerEngine:
    """
    Production inference engine maintaining per-vehicle rolling temporal buffers.
    Transforms rolling GPS + telemetry history into Transformer-derived features.
    """

    def __init__(self, model_path: Optional[str] = None) -> None:
        self.model_path = model_path or "results/models/temporal_transformer.pt"
        self.model: Optional[TrajectoryTemporalTransformer] = None
        self.is_trained: bool = False
        
        # Per-vehicle historical step buffers: vehicle_id -> list of feature dicts
        self.buffers: Dict[str, List[Dict[str, float]]] = {}
        self.seq_len = TrajectoryTemporalTransformer.SEQ_LEN

        self._initialize_model()

    def _initialize_model(self) -> None:
        if not TORCH_AVAILABLE:
            self.model = None
            self.is_trained = False
            return

        self.model = TrajectoryTemporalTransformer()
        p = Path(self.model_path)
        if p.exists():
            try:
                state_dict = torch.load(p, map_location="cpu")
                self.model.load_state_dict(state_dict)
                self.model.eval()
                self.is_trained = True
            except Exception as e:
                print(f"[TemporalTransformerEngine] Checkpoint load warning: {e}")
                self.is_trained = False
        else:
            # Checkpoint not yet trained
            self.is_trained = False

    def record_step(self, vehicle_id: str, telemetry: Dict[str, Any]) -> None:
        """Appends a new normalized observation step into vehicle's temporal buffer."""
        if vehicle_id not in self.buffers:
            self.buffers[vehicle_id] = []
        
        feat = self._normalize_telemetry(telemetry)
        buf = self.buffers[vehicle_id]
        buf.append(feat)
        if len(buf) > self.seq_len:
            self.buffers[vehicle_id] = buf[-self.seq_len:]

    def _normalize_telemetry(self, t: Dict[str, Any]) -> Dict[str, float]:
        """Normalizes real telemetry parameters into [0, 1] feature bounds."""
        lat = float(t.get("latitude", t.get("lat", 0.0)))
        lon = float(t.get("longitude", t.get("lon", 0.0)))
        speed = float(t.get("speed_kmh", t.get("speed", 0.0)))
        heading = float(t.get("heading", 0.0))
        fuel = float(t.get("fuel_level", t.get("fuel", 100.0)))
        traffic = float(t.get("traffic_level_norm", 0.2))
        road_friction = float(t.get("road_friction", 0.1))
        eta = float(t.get("eta_mins", 30.0))
        prog = float(t.get("route_progress", 0.0))
        urgency = float(t.get("urgency", 0.5))
        conn = 1.0 if t.get("connectivity") == "CLOUD_MODE" else (0.5 if t.get("connectivity") == "MESH_MODE" else 0.0)
        condition = float(t.get("vehicle_condition", 1.0))

        return {
            "lat_norm": float(np.clip(lat / 90.0, -1.0, 1.0)),
            "lon_norm": float(np.clip(lon / 180.0, -1.0, 1.0)),
            "speed_norm": float(np.clip(speed / 100.0, 0.0, 1.5)),
            "heading_norm": float(np.clip(heading / 360.0, 0.0, 1.0)),
            "fuel_norm": float(np.clip(fuel / 100.0, 0.0, 1.0)),
            "traffic_norm": float(np.clip(traffic, 0.0, 1.0)),
            "road_friction": float(np.clip(road_friction, 0.0, 1.0)),
            "eta_mins_norm": float(np.clip(eta / 120.0, 0.0, 2.0)),
            "route_progress": float(np.clip(prog, 0.0, 1.0)),
            "urgency_norm": float(np.clip(urgency, 0.0, 2.0)),
            "connectivity_code": conn,
            "vehicle_condition_norm": float(np.clip(condition, 0.0, 1.0)),
        }

    def infer(self, vehicle_id: str) -> Dict[str, Any]:
        """
        Executes forward inference over vehicle's historical sequence.
        Returns extracted dynamic features and reroute desirability signal.
        """
        if not TORCH_AVAILABLE or self.model is None:
            return {
                "status": "MODEL_UNAVAILABLE",
                "reason": "PyTorch or Transformer architecture unavailable",
                "embedding": [0.0] * TrajectoryTemporalTransformer.HIDDEN_DIM,
                "trends": {
                    "speed_trend": 0.0,
                    "fuel_drain_trend": 0.0,
                    "delay_risk": 0.0,
                    "reroute_desirability": 0.0,
                },
            }

        if not self.is_trained:
            return {
                "status": "TRANSFORMER_NOT_TRAINED",
                "reason": f"No validated Transformer checkpoint found at {self.model_path}",
                "embedding": [0.0] * TrajectoryTemporalTransformer.HIDDEN_DIM,
                "trends": {
                    "speed_trend": 0.0,
                    "fuel_drain_trend": 0.0,
                    "delay_risk": 0.0,
                    "reroute_desirability": 0.0,
                },
            }

        buf = self.buffers.get(vehicle_id, [])
        if not buf:
            return {
                "status": "INSUFFICIENT_HISTORY",
                "steps_collected": 0,
                "embedding": [0.0] * TrajectoryTemporalTransformer.HIDDEN_DIM,
                "trends": {
                    "speed_trend": 0.0,
                    "fuel_drain_trend": 0.0,
                    "delay_risk": 0.0,
                    "reroute_desirability": 0.0,
                },
            }

        # Pad sequence with earliest frame if fewer than SEQ_LEN frames exist
        seq_features = []
        first_frame = buf[0]
        padding_count = max(0, self.seq_len - len(buf))
        for _ in range(padding_count):
            seq_features.append([first_frame[fn] for fn in TrajectoryTemporalTransformer.FEATURE_NAMES])
        for frame in buf[-self.seq_len:]:
            seq_features.append([frame[fn] for fn in TrajectoryTemporalTransformer.FEATURE_NAMES])

        inp_array = np.array(seq_features, dtype=np.float32)[np.newaxis, :, :]  # [1, SEQ_LEN, INPUT_DIM]
        inp_tensor = torch.from_numpy(inp_array)

        with torch.no_grad():
            emb, trends = self.model(inp_tensor)
            emb_list = emb.squeeze(0).cpu().numpy().tolist()
            trend_vals = trends.squeeze(0).cpu().numpy()

        return {
            "status": "SUCCESS",
            "steps_evaluated": len(buf),
            "embedding": emb_list,
            "trends": {
                "speed_trend": round(float(trend_vals[0]), 4),
                "fuel_drain_trend": round(float(trend_vals[1]), 4),
                "delay_risk": round(float(trend_vals[2]), 4),
                "reroute_desirability": round(float(trend_vals[3]), 4),
            },
        }


# Global temporal transformer singleton
temporal_transformer = TemporalTransformerEngine()
