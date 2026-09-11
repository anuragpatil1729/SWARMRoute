"""
FastAPI Server for SWARMRoute Live Dashboard.
Exposes REST and SSE endpoints connected directly to the real simulation engine.
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from src.api.simulation_runner import runner
from src.api.supabase_service import supabase_service


app = FastAPI(
    title="SWARMRoute Live Simulation API",
    description="Operational API connecting Next.js dashboard directly to the real SWARMRoute fleet engine.",
    version="1.0.0",
)

# Enable CORS for Next.js frontend (read from CORS_ALLOWED_ORIGINS, defaulting to local dev)
cors_env = os.getenv("CORS_ALLOWED_ORIGINS", "http://localhost:3000")
allowed_origins = [origin.strip() for origin in cors_env.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ResetRequest(BaseModel):
    dataset: str = "C101"
    customers: int = 20
    vehicles: int = 4
    seed: int = 42
    horizon: float = 1200.0
    city: Optional[str] = None


class CityRequest(BaseModel):
    city: str


class SpeedRequest(BaseModel):
    speed: float = 1.0


class BreakRequest(BaseModel):
    vehicle_id: Optional[str] = None


class CloudRequest(BaseModel):
    enabled: Optional[bool] = None


class TrafficRequest(BaseModel):
    u: Optional[int] = None
    v: Optional[int] = None
    level: str = "SEVERE"


class DemandRequest(BaseModel):
    zone: str = "North-East"


class AllocateRequest(BaseModel):
    order_id: str
    vehicle_id: str


class CompleteRequest(BaseModel):
    order_id: str
    vehicle_id: Optional[str] = None


@app.get("/api/health")
def health_check() -> Dict[str, Any]:
    return {
        "status": "ONLINE",
        "service": "SWARMRoute Autonomous Simulation Engine",
        "simulation_status": runner.status,
        "dataset": runner.dataset,
    }


@app.get("/api/state")
def get_state() -> Dict[str, Any]:
    return runner.get_state()


@app.get("/api/stream")
async def event_stream(request: Request) -> StreamingResponse:
    """Server-Sent Events (SSE) streaming real-time simulation frames to dashboard."""
    async def event_generator():
        while True:
            if await request.is_disconnected():
                break
            try:
                state_data = runner.get_state()
                payload = json.dumps(state_data)
                yield f"data: {payload}\n\n"
            except Exception as e:
                yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"
            await asyncio.sleep(0.35)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/simulation/start")
def start_simulation() -> Dict[str, Any]:
    runner.start()
    return {"status": runner.status}


@app.post("/api/simulation/pause")
def pause_simulation() -> Dict[str, Any]:
    runner.pause()
    return {"status": runner.status}


@app.post("/api/simulation/step")
def step_simulation() -> Dict[str, Any]:
    return runner.step()


@app.post("/api/simulation/reset")
def reset_simulation(req: Optional[ResetRequest] = None) -> Dict[str, Any]:
    if req is None:
        req = ResetRequest()
    return runner.reset(
        dataset=req.dataset,
        customers=req.customers,
        vehicles=req.vehicles,
        seed=req.seed,
        horizon=req.horizon,
        city=req.city,
    )


@app.post("/api/simulation/city")
def set_simulation_city(req: CityRequest) -> Dict[str, Any]:
    runner.set_city(req.city)
    return {"status": "SUCCESS", "city": runner.city}


@app.post("/api/simulation/speed")
def set_simulation_speed(req: SpeedRequest) -> Dict[str, Any]:
    runner.set_speed(req.speed)
    return {"speed": runner.speed}


@app.post("/api/disruption/break")
def inject_breakdown(req: Optional[BreakRequest] = None) -> Dict[str, Any]:
    vid = req.vehicle_id if req else None
    return runner.break_vehicle(vehicle_id=vid)


@app.post("/api/disruption/cloud")
def toggle_cloud(req: Optional[CloudRequest] = None) -> Dict[str, Any]:
    enabled = req.enabled if req else None
    return runner.toggle_cloud(enabled=enabled)


@app.post("/api/disruption/traffic")
def inject_traffic(req: Optional[TrafficRequest] = None) -> Dict[str, Any]:
    if req is None:
        req = TrafficRequest()
    return runner.inject_traffic(u=req.u, v=req.v, level=req.level)


@app.post("/api/disruption/demand")
def inject_demand_burst(req: Optional[DemandRequest] = None) -> Dict[str, Any]:
    zone = req.zone if req else "North-East"
    return runner.inject_demand_burst(zone=zone)


@app.post("/api/disruption/combined")
def inject_combined() -> Dict[str, Any]:
    return runner.inject_combined_disruption()


@app.get("/api/benchmarks")
def get_benchmarks() -> JSONResponse:
    """Serves empirical benchmark comparison directly from results."""
    bm_path = Path("results/benchmarks/final_comparison.json")
    if bm_path.exists():
        with open(bm_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return JSONResponse(content=data)
    return JSONResponse(content={"error": "Benchmark results not found"}, status_code=404)


@app.get("/api/ppo/history")
def get_ppo_history() -> Dict[str, Any]:
    return {
        "history": runner.ppo_history,
        "cumulative_reward": runner.cumulative_ppo_reward,
        "last_action_idx": runner.last_ppo_action_idx,
    }


@app.post("/api/task/allocate")
def allocate_task(req: AllocateRequest) -> Dict[str, Any]:
    """Allocates an order to a delivery partner vehicle and syncs to Supabase."""
    res = runner.allocate_order(order_id=req.order_id, vehicle_id=req.vehicle_id)
    if res.get("success"):
        supabase_service.record_task_allocation(order_id=req.order_id, vehicle_id=req.vehicle_id)
    return res


@app.post("/api/task/complete")
def complete_task(req: CompleteRequest) -> Dict[str, Any]:
    """Marks an order as delivered by the partner, unloads cargo, and updates Supabase."""
    res = runner.complete_order(order_id=req.order_id, vehicle_id=req.vehicle_id)
    if res.get("success"):
        supabase_service.record_task_completion(order_id=req.order_id, vehicle_id=req.vehicle_id)
    return res


@app.get("/api/partners")
def get_delivery_partners() -> Dict[str, Any]:
    """Returns active delivery partner profiles with live vehicle telemetry."""
    return {"partners": runner.get_delivery_partners()}


@app.get("/api/supabase/status")
def get_supabase_status() -> Dict[str, Any]:
    """Returns live Supabase PostgreSQL connection status and metrics."""
    return supabase_service.get_status()

