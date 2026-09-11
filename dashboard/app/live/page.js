"use client";

import { useState } from "react";
import Link from "next/link";
import Section from "../../components/Section";
import Stat from "../../components/Stat";
import OpenStreetMap from "../../components/OpenStreetMap";
import { useDashboardState } from "../../lib/useDashboardState";
import { useAuth } from "../../lib/AuthContext";

export default function LivePage() {
  const {
    state,
    connectionStatus,
    start,
    pause,
    step,
    reset,
    breakVehicle,
    toggleCloud,
    injectTraffic,
    injectCombined,
  } = useDashboardState();
  const { role } = useAuth();

  const [selectedVehicleId, setSelectedVehicleId] = useState(null);

  // If a Delivery Partner visits Manager deck, guide them to their cockpit
  if (role === "partner") {
    return (
      <div className="py-16 text-center max-w-lg mx-auto">
        <div className="border border-slate-200 bg-white rounded-2xl shadow-sm p-8">
          <span className="text-3xl">🛵</span>
          <h2 className="text-lg font-bold text-slate-900 mt-2">Delivery Partner Account</h2>
          <p className="text-xs text-slate-500 mt-2 leading-relaxed">
            You are logged in as a Delivery Partner. The Manager Dispatch Deck is reserved for central fleet operations.
          </p>
          <Link
            href="/partner"
            className="inline-block mt-4 px-4 py-2 text-xs font-bold text-white bg-emerald-600 hover:bg-emerald-700 rounded-lg transition shadow-xs"
          >
            Open My Partner Delivery Cockpit →
          </Link>
        </div>
      </div>
    );
  }

  // Offline / Loading State Handling
  if (connectionStatus === "OFFLINE" && !state) {
    return (
      <div className="py-16 text-center">
        <div className="border border-red-200 bg-white rounded-2xl shadow-sm p-8 max-w-lg mx-auto">
          <div className="font-mono text-xs text-red-600 font-bold uppercase tracking-wider">
            Connection Offline
          </div>
          <h2 className="text-xl font-bold text-slate-900 mt-2">SIMULATION OFFLINE</h2>
          <p className="text-xs text-slate-500 mt-2 leading-relaxed">
            The live simulation backend at <code className="font-mono bg-slate-100 px-1 py-0.5 rounded text-slate-700">http://127.0.0.1:8000</code> is currently unreachable.
          </p>
          <div className="mt-4 p-3 bg-slate-50 border border-slate-200 rounded-lg text-left font-mono text-xs">
            <span className="text-slate-400"># Start backend engine in terminal:</span>
            <br />
            <span className="text-slate-800 font-semibold">python scripts/run_dashboard_backend.py</span>
          </div>
        </div>
      </div>
    );
  }

  if (!state) {
    return (
      <div className="py-16 text-center">
        <div className="border border-slate-200 bg-white rounded-2xl shadow-sm p-8 max-w-md mx-auto">
          <div className="font-mono text-xs text-slate-400">Status</div>
          <h2 className="text-xl font-bold text-slate-800 mt-1">CONNECTING TO SIMULATION</h2>
          <p className="text-xs text-slate-500 mt-2">Streaming real-time operational telemetry feed...</p>
        </div>
      </div>
    );
  }

  const {
    simulation,
    fleet,
    vehicles = [],
    orders = [],
    map: mapData,
    traffic,
    network,
    incidents = [],
    recovery_flow = [],
    ppo = {},
    sustainability,
    performance,
    events = [],
  } = state;

  const isRunning = simulation.status === "RUNNING";
  const selectedVehicle = vehicles.find((v) => v.id === selectedVehicleId);

  // 1. KPI Calculations (Section 2)
  const activeDeliveriesCount = orders.filter(
    (o) => o.status === "IN_TRANSIT" || o.status === "ASSIGNED" || o.status === "PENDING"
  ).length;
  const delayedOrFailedCount = (performance.late || 0) + (performance.failed || 0);

  // 2. System Status (Section 5)
  const isCloudOnline = network?.cloud_status === "ONLINE";
  const isMeshActive = network?.mesh_status === "ACTIVE";
  const activeIncidents = incidents.filter(
    (i) => i.status !== "RESOLVED" && i.recovery_status !== "RECOVERED"
  );
  const brokenVehicle = vehicles.find((v) => v.status === "BROKEN_DOWN");
  const hasActiveIncident = activeIncidents.length > 0 || fleet.broken > 0;

  const primaryIncident = activeIncidents[0] || (brokenVehicle ? {
    vehicle_id: brokenVehicle.id,
    type: "VEHICLE_BREAKDOWN",
    stranded_orders: brokenVehicle.assigned_orders?.length ?? null,
    recovery_vehicle: null,
    recovery_status: "IN PROGRESS",
    recovery_time_sec: null,
  } : null);

  // 3. Live Event Feed (Section 7: Latest 5-7 events)
  const recentEvents = events.slice(0, 7);

  // 4. Last Autonomous Decision (Section 8: 100% Real PPO / Agent Data)
  const ppoHistory = ppo?.history || [];
  const latestDecision = ppoHistory.length > 0 ? ppoHistory[ppoHistory.length - 1] : null;
  const lastDecision = latestDecision ? {
    action: latestDecision.action || null,
    vehicle: latestDecision.target || latestDecision.vehicle || null,
    order: latestDecision.order_id || latestDecision.order || null,
    reason: latestDecision.reason || null,
    time: latestDecision.time_str || (latestDecision.time !== undefined ? `${latestDecision.time}m` : null),
  } : null;

  return (
    <div className="space-y-6 w-full">
      {/* Simulation Master Header & Control Strip */}
      <div className="border border-slate-200 bg-white rounded-xl shadow-sm p-4">
        <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
          <div className="flex items-center gap-3 flex-wrap">
            <h2 className="text-lg font-bold text-slate-900 tracking-tight">
              Operational Fleet Overview
            </h2>
            <span
              className={`font-mono text-[11px] px-2.5 py-0.5 rounded-full font-semibold ${
                connectionStatus === "CONNECTED"
                  ? "text-emerald-700 bg-emerald-50 border border-emerald-200"
                  : "text-red-700 bg-red-50 border border-red-200"
              }`}
            >
              ● {connectionStatus}
            </span>
            <span className="font-mono text-[11px] px-2.5 py-0.5 rounded-full border border-slate-200 text-slate-700 bg-slate-50 font-semibold">
              {simulation.time_str} · {simulation.status}
            </span>
            <span className="text-[11px] font-mono text-slate-500">
              Location: {simulation?.hub || simulation?.city || simulation?.region || simulation?.scenario || "Active Simulation"}
            </span>
          </div>

          {/* Controls: Playback & Demo Disruption Injectors */}
          <div className="flex flex-wrap items-center gap-2 font-mono text-xs">
            {isRunning ? (
              <button
                onClick={pause}
                className="px-3.5 py-1.5 rounded-lg border border-slate-300 bg-white hover:bg-slate-50 text-slate-800 font-bold shadow-xs transition"
              >
                PAUSE
              </button>
            ) : (
              <button
                onClick={start}
                className="px-3.5 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-bold shadow-xs transition"
              >
                START
              </button>
            )}
            <button
              onClick={step}
              disabled={isRunning}
              className={`px-3 py-1.5 rounded-lg border border-slate-200 bg-slate-50 text-slate-700 font-semibold ${
                isRunning ? "opacity-40 cursor-not-allowed" : "hover:bg-slate-100"
              }`}
            >
              STEP
            </button>
            <button
              onClick={() => reset()}
              className="px-3 py-1.5 rounded-lg border border-slate-200 bg-slate-50 hover:bg-slate-100 text-slate-600 font-semibold"
            >
              RESET
            </button>

            {/* Quick Disruption Demonstrator Buttons */}
            <div className="hidden sm:flex items-center gap-1.5 pl-2 border-l border-slate-200">
              <button
                onClick={() => breakVehicle()}
                className="px-2.5 py-1.5 rounded-lg bg-red-50 hover:bg-red-100 text-red-700 border border-red-200 text-[11px] font-semibold transition"
                title="Simulate truck mechanical breakdown"
              >
                ⚡ Breakdown
              </button>
              <button
                onClick={() => toggleCloud(!isCloudOnline)}
                className="px-2.5 py-1.5 rounded-lg bg-amber-50 hover:bg-amber-100 text-amber-800 border border-amber-200 text-[11px] font-semibold transition"
                title="Toggle cloud vs peer-to-peer mesh mode"
              >
                ☁️ {isCloudOnline ? "Cut Cloud" : "Restore Cloud"}
              </button>
              <button
                onClick={() => injectTraffic(null, null, "SEVERE")}
                className="px-2.5 py-1.5 rounded-lg bg-orange-50 hover:bg-orange-100 text-orange-800 border border-orange-200 text-[11px] font-semibold transition"
                title="Inject severe traffic bottleneck"
              >
                🚦 Traffic
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* SECTION 2: TOP-LEVEL OPERATIONAL KPI ROW */}
      <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-3">
        <Stat
          label="Active Vehicles"
          value={`${fleet.available} / ${fleet.size}`}
          help={fleet.broken > 0 ? `${fleet.broken} broken down` : "All operational"}
        />
        <Stat
          label="Active Deliveries"
          value={activeDeliveriesCount}
          help="In-transit or assigned"
        />
        <Stat
          label="Delivered Orders"
          value={performance.delivered}
          help={`${performance.success_rate}% success rate`}
        />
        <Stat
          label="Late / Failed"
          value={delayedOrFailedCount}
          help={`${performance.late} late · ${performance.failed} failed`}
        />
        <Stat
          label="Fleet Utilization"
          value={`${Math.round(performance.fleet_utilization_pct || fleet.utilization_pct || 0)}%`}
          help="Payload capacity usage"
        />
        <Stat
          label="Fuel Used"
          value={`${Math.round(sustainability.fuel_liters || fleet.total_fuel_l || 0)} L`}
          help="Total fleet consumption"
        />
        <Stat
          label="CO₂ Emitted"
          value={`${Math.round(sustainability.co2_kg || fleet.total_co2_kg || 0)} kg`}
          help="Carbon footprint"
        />
      </div>

      {/* MAIN CONTENT: 2-COLUMN OPERATIONAL GRID */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start">
        {/* LEFT COLUMN: LIVE FLEET MAP & LIVE EVENTS (2 cols wide) */}
        <div className="lg:col-span-2 space-y-6">
          {/* SECTION 3: LIVE FLEET MAP (PRIMARY ELEMENT) */}
          <div className="border border-slate-200 bg-white rounded-xl shadow-sm p-4">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3 mb-3">
              <div>
                <h3 className="text-sm font-bold text-slate-900 uppercase font-mono flex items-center gap-2">
                  <span>🗺️</span>
                  <span>Live GIS Fleet Map — {simulation?.city ? `${simulation.city} Operations` : simulation?.hub || simulation?.scenario || "Active Fleet Operations"}</span>
                </h3>
                <p className="text-xs text-slate-400 font-mono mt-0.5">
                  Click any vehicle to inspect real-time telematics on demand
                </p>
              </div>

              {/* Map Legend */}
              <div className="hidden sm:flex items-center gap-3 text-[11px] font-mono text-slate-600">
                <span className="flex items-center gap-1">
                  <span className="w-2.5 h-2.5 rounded-full bg-blue-600" /> Active Route
                </span>
                <span className="flex items-center gap-1">
                  <span className="w-2.5 h-2.5 rounded-full bg-red-600" /> Broken Down
                </span>
                <span className="flex items-center gap-1">
                  <span className="w-2.5 h-2.5 rounded-full bg-amber-500" /> Congestion
                </span>
              </div>
            </div>

            {/* Map Container */}
            <div className="h-[440px] w-full rounded-xl overflow-hidden border border-slate-200 relative">
              <OpenStreetMap
                customers={mapData?.customers || []}
                depot={mapData?.depot || { x: 40, y: 50 }}
                routes={mapData?.active_routes || {}}
                recoveryRoutes={mapData?.recovery_routes || {}}
                vehicles={vehicles}
                trafficEdges={mapData?.traffic_edges || []}
                selectedVehicleId={selectedVehicleId}
                onSelectVehicle={(vid) => setSelectedVehicleId(vid)}
              />
            </div>
          </div>

          {/* SECTION 7: LIVE EVENT FEED */}
          <div className="border border-slate-200 bg-white rounded-xl shadow-sm p-4">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3 mb-3">
              <div>
                <h3 className="text-sm font-bold text-slate-900 uppercase font-mono flex items-center gap-2">
                  <span>⚡</span>
                  <span>Live Event Feed</span>
                </h3>
                <p className="text-xs text-slate-400 font-mono mt-0.5">
                  Chronological record of recent system disruptions, dispatches, and deliveries
                </p>
              </div>
              <span className="text-[11px] font-mono text-slate-500">Latest 7 Events</span>
            </div>

            <div className="space-y-2 font-mono text-xs max-h-56 overflow-y-auto">
              {recentEvents.length > 0 ? (
                recentEvents.map((ev, idx) => {
                  const isBreakdown = ev.type === "BREAKDOWN";
                  const isRecovery = ev.type?.includes("RECOVERY") || ev.type?.includes("REASSIGN");
                  const isDelivered = ev.type?.includes("DELIVERED") || ev.type?.includes("COMPLETE");
                  return (
                    <div
                      key={idx}
                      className={`p-2.5 rounded-lg border flex items-center justify-between gap-3 ${
                        isBreakdown
                          ? "bg-red-50/70 border-red-200 text-red-900"
                          : isRecovery
                          ? "bg-purple-50/70 border-purple-200 text-purple-900"
                          : isDelivered
                          ? "bg-emerald-50/70 border-emerald-200 text-emerald-900"
                          : "bg-slate-50 border-slate-200 text-slate-800"
                      }`}
                    >
                      <div className="flex items-center gap-2.5 min-w-0">
                        <span className="text-slate-400 text-[11px] whitespace-nowrap">
                          {ev.time_str || `${ev.timestamp}m`}
                        </span>
                        <span
                          className={`px-1.5 py-0.5 rounded text-[10px] font-bold whitespace-nowrap ${
                            isBreakdown
                              ? "bg-red-200 text-red-900"
                              : isRecovery
                              ? "bg-purple-200 text-purple-900"
                              : isDelivered
                              ? "bg-emerald-200 text-emerald-900"
                              : "bg-slate-200 text-slate-700"
                          }`}
                        >
                          {ev.type}
                        </span>
                        <span className="truncate text-xs font-sans text-slate-700">
                          {ev.description}
                        </span>
                      </div>
                      <span className="text-[10px] text-slate-400 whitespace-nowrap hidden sm:inline">
                        {ev.target || "Fleet"}
                      </span>
                    </div>
                  );
                })
              ) : (
                <div className="text-center py-6 text-xs text-slate-400 font-mono">
                  Simulation initialized. Operational events will stream here automatically.
                </div>
              )}
            </div>
          </div>
        </div>

        {/* RIGHT COLUMN: SYSTEM STATUS, ACTIVE INCIDENT, LAST DECISION, VEHICLE DETAILS */}
        <div className="space-y-6">
          {/* SECTION 5: COMPACT SYSTEM STATUS */}
          <div className="border border-slate-200 bg-white rounded-xl shadow-sm p-4">
            <div className="border-b border-slate-100 pb-2.5 mb-3 flex items-center justify-between">
              <h3 className="text-xs font-bold text-slate-900 uppercase font-mono">
                System Status
              </h3>
              <span className="text-[10px] font-mono text-slate-400">Autonomous Mesh</span>
            </div>

            <div className="grid grid-cols-2 gap-3 text-xs font-mono">
              <div className="p-3 rounded-lg bg-slate-50 border border-slate-200">
                <span className="text-[10px] text-slate-400 uppercase block">Fleet</span>
                <span className="text-sm font-bold text-slate-800">
                  {fleet.available} / {fleet.size} Operational
                </span>
                <span className="text-[10px] text-slate-500 block mt-0.5">
                  {fleet.broken > 0 ? `${fleet.broken} down` : "All ready"}
                </span>
              </div>

              <div className="p-3 rounded-lg bg-slate-50 border border-slate-200">
                <span className="text-[10px] text-slate-400 uppercase block">Connectivity</span>
                <div className="flex items-center gap-2 mt-0.5">
                  <span className={`font-bold ${isCloudOnline ? "text-blue-600" : "text-slate-400"}`}>
                    Cloud {isCloudOnline ? "●" : "○"}
                  </span>
                  <span className="text-slate-300">|</span>
                  <span className={`font-bold ${isMeshActive ? "text-emerald-600" : "text-slate-400"}`}>
                    Mesh ●
                  </span>
                </div>
                <span className="text-[10px] text-slate-500 block mt-0.5">
                  {isCloudOnline ? "Cloud Uplink Normal" : "Peer Mesh Engaged"}
                </span>
              </div>

              <div className="p-3 rounded-lg bg-slate-50 border border-slate-200">
                <span className="text-[10px] text-slate-400 uppercase block">Traffic</span>
                <span
                  className={`text-sm font-bold ${
                    traffic?.congestion_level === "SEVERE"
                      ? "text-red-600"
                      : traffic?.congestion_level === "HEAVY"
                      ? "text-amber-600"
                      : "text-emerald-600"
                  }`}
                >
                  {traffic?.congestion_level || "NORMAL"}
                </span>
                <span className="text-[10px] text-slate-500 block mt-0.5">
                  {traffic?.affected_roads?.length || 0} corridors congested
                </span>
              </div>

              <div className="p-3 rounded-lg bg-slate-50 border border-slate-200">
                <span className="text-[10px] text-slate-400 uppercase block">Incident</span>
                <span
                  className={`text-sm font-bold ${
                    hasActiveIncident ? "text-red-600 animate-pulse" : "text-emerald-600"
                  }`}
                >
                  {hasActiveIncident ? "ACTIVE" : "NONE"}
                </span>
                <span className="text-[10px] text-slate-500 block mt-0.5">
                  {hasActiveIncident ? "Breakdown / SOS" : "Peace-time cruise"}
                </span>
              </div>
            </div>
          </div>

          {/* SECTION 6: ACTIVE INCIDENT / SELF-HEALING (CONTEXTUAL) */}
          <div className="border border-slate-200 bg-white rounded-xl shadow-sm p-4">
            <div className="border-b border-slate-100 pb-2.5 mb-3 flex items-center justify-between">
              <h3 className="text-xs font-bold text-slate-900 uppercase font-mono flex items-center gap-1.5">
                <span>🛡️</span>
                <span>Active Incident & Self-Healing</span>
              </h3>
              {hasActiveIncident ? (
                <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-red-100 text-red-800 border border-red-200 animate-pulse font-mono">
                  DISRUPTION ACTIVE
                </span>
              ) : (
                <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200 font-mono">
                  NOMINAL
                </span>
              )}
            </div>

            {!hasActiveIncident || !primaryIncident ? (
              <div className="p-4 rounded-lg bg-emerald-50/60 border border-emerald-200/80 text-center font-mono">
                <span className="text-emerald-700 font-bold text-xs uppercase block">
                  ✓ NO ACTIVE INCIDENTS
                </span>
                <p className="text-[11px] text-emerald-800/80 mt-1 font-sans">
                  All fleet vehicles operating normally. Peer heartbeats active.
                </p>
              </div>
            ) : (
              <div className="space-y-3 font-mono">
                {/* Incident Summary Card */}
                <div className="p-3.5 rounded-lg bg-red-50 border border-red-200 text-red-950">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-xs uppercase text-red-700 flex items-center gap-1.5">
                      <span>⚠️</span> {primaryIncident.vehicle_id ? `${primaryIncident.vehicle_id} BREAKDOWN` : "VEHICLE BREAKDOWN"}
                    </span>
                    <span className="text-[10px] px-2 py-0.5 rounded bg-red-200 font-bold text-red-900 uppercase">
                      {primaryIncident.recovery_status || "IN PROGRESS"}
                    </span>
                  </div>

                  <div className="grid grid-cols-2 gap-2 text-xs mt-3 pt-2.5 border-t border-red-200/60">
                    <div>
                      <span className="text-[10px] text-red-600 block">Affected Orders:</span>
                      <span className="font-bold text-red-900 text-sm">
                        {Array.isArray(primaryIncident.stranded_orders)
                          ? `${primaryIncident.stranded_orders.length} affected`
                          : primaryIncident.stranded_orders !== null && primaryIncident.stranded_orders !== undefined
                          ? `${primaryIncident.stranded_orders} affected`
                          : "—"}
                      </span>
                    </div>
                    <div>
                      <span className="text-[10px] text-red-600 block">Recovery Vehicle:</span>
                      <span className="font-bold text-red-900 text-sm">
                        {primaryIncident.recovery_vehicle || "Searching peer..."}
                      </span>
                    </div>
                  </div>

                  {primaryIncident.recovery_time_sec !== undefined && primaryIncident.recovery_time_sec !== null && (
                    <div className="mt-2 text-[10px] text-red-700">
                      Recovery Time: <span className="font-bold">{primaryIncident.recovery_time_sec}s</span>
                    </div>
                  )}
                </div>

                {/* 5-Step Recovery Pipeline (FAILURE → SOS → MESH → REASSIGN → RECOVERY) */}
                <div className="p-3 rounded-lg bg-slate-50 border border-slate-200">
                  <div className="text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-2">
                    Mesh Self-Healing Protocol
                  </div>
                  <div className="grid grid-cols-5 gap-1 text-center text-[10px] font-mono">
                    {[
                      { name: "FAILURE", active: true },
                      { name: "SOS", active: true },
                      { name: "MESH", active: isMeshActive || primaryIncident.recovery_status !== undefined },
                      { name: "REASSIGN", active: !!primaryIncident.recovery_vehicle || primaryIncident.recovery_status === "RECOVERED" },
                      { name: "RECOVERY", active: primaryIncident.recovery_status === "RECOVERED" || primaryIncident.recovery_status === "COMPLETE" },
                    ].map((stepItem, sIdx) => (
                      <div
                        key={sIdx}
                        className={`py-1.5 px-1 rounded border text-[10px] font-bold ${
                          stepItem.active
                            ? "bg-blue-600 text-white border-blue-700 shadow-xs"
                            : "bg-slate-100 text-slate-400 border-slate-200"
                        }`}
                      >
                        {stepItem.name}
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* SECTION 8: LAST AUTONOMOUS DECISION */}
          <div className="border border-slate-200 bg-white rounded-xl shadow-sm p-4">
            <div className="border-b border-slate-100 pb-2.5 mb-3 flex items-center justify-between">
              <h3 className="text-xs font-bold text-slate-900 uppercase font-mono flex items-center gap-1.5">
                <span>🤖</span>
                <span>Last Autonomous Decision</span>
              </h3>
              <Link
                href="/ai"
                className="text-[11px] font-mono text-blue-600 hover:text-blue-700 font-semibold"
              >
                Inspect AI →
              </Link>
            </div>

            {lastDecision ? (
              <div className="p-3.5 rounded-lg bg-slate-50 border border-slate-200 font-mono text-xs space-y-2">
                <div className="flex items-center justify-between">
                  <span className="font-bold text-slate-900 text-sm text-blue-700">
                    {lastDecision.action || "—"}
                  </span>
                  <span className="text-[10px] text-slate-400">{lastDecision.time || "—"}</span>
                </div>

                <div className="grid grid-cols-2 gap-2 text-[11px] pt-1 border-t border-slate-200/60 text-slate-600">
                  <div>
                    <span className="text-[10px] text-slate-400 block">Vehicle:</span>
                    <span className="font-bold text-slate-800">{lastDecision.vehicle || "—"}</span>
                  </div>
                  <div>
                    <span className="text-[10px] text-slate-400 block">Target Order:</span>
                    <span className="font-bold text-slate-800">{lastDecision.order || "—"}</span>
                  </div>
                </div>

                {lastDecision.reason && (
                  <div className="text-[11px] pt-1 text-slate-500">
                    <span className="text-[10px] text-slate-400 block font-sans">Reason:</span>
                    <span className="text-slate-700 font-medium font-sans">{lastDecision.reason}</span>
                  </div>
                )}
              </div>
            ) : (
              <div className="p-4 rounded-lg bg-slate-50 border border-slate-200 text-center font-mono text-xs">
                <span className="text-slate-600 font-bold uppercase block">
                  NO AUTONOMOUS DECISION YET
                </span>
                <p className="text-[11px] text-slate-400 mt-1 font-sans">
                  The dispatch agent will record decisions when interventions occur.
                </p>
              </div>
            )}
          </div>

          {/* SECTION 4: VEHICLE DETAILS (ON-DEMAND WHEN CLICKED) */}
          {selectedVehicle && (
            <div className="border border-blue-200 bg-blue-50/40 rounded-xl shadow-sm p-4 relative animate-in fade-in duration-200">
              <div className="flex items-center justify-between border-b border-blue-200/80 pb-2.5 mb-3">
                <div className="flex items-center gap-2">
                  <span className="text-lg">{selectedVehicle.avatar || "🚚"}</span>
                  <div>
                    <h3 className="text-xs font-bold text-slate-900 font-mono">
                      {selectedVehicle.partner_name || selectedVehicle.id}
                    </h3>
                    <div className="text-[10px] text-slate-500 font-mono">
                      {selectedVehicle.id} · {selectedVehicle.vehicle_model}
                    </div>
                  </div>
                </div>
                <button
                  onClick={() => setSelectedVehicleId(null)}
                  className="w-5 h-5 flex items-center justify-center rounded-full bg-slate-200 hover:bg-slate-300 text-slate-600 text-xs font-bold"
                  title="Close vehicle panel"
                >
                  ✕
                </button>
              </div>

              {/* On-Demand Vehicle Attributes (Section 4 specs) */}
              <div className="grid grid-cols-2 gap-2 font-mono text-[11px]">
                <div className="p-2 rounded bg-white border border-slate-200">
                  <span className="text-[10px] text-slate-400 block">Status:</span>
                  <span className="font-bold text-slate-800">{selectedVehicle.status}</span>
                </div>

                <div className="p-2 rounded bg-white border border-slate-200">
                  <span className="text-[10px] text-slate-400 block">Speed:</span>
                  <span className="font-bold text-slate-800">{Math.round(selectedVehicle.speed_kmh)} km/h</span>
                </div>

                <div className="p-2 rounded bg-white border border-slate-200">
                  <span className="text-[10px] text-slate-400 block">Current Load:</span>
                  <span className="font-bold text-slate-800">{selectedVehicle.current_load} / {selectedVehicle.max_weight} kg</span>
                </div>

                <div className="p-2 rounded bg-white border border-slate-200">
                  <span className="text-[10px] text-slate-400 block">Rem. Capacity:</span>
                  <span className="font-bold text-slate-800">{selectedVehicle.remaining_capacity} kg</span>
                </div>

                <div className="p-2 rounded bg-white border border-slate-200">
                  <span className="text-[10px] text-slate-400 block">Battery / Fuel:</span>
                  <span className="font-bold text-slate-800">{Math.round(selectedVehicle.fuel_level)}%</span>
                </div>

                <div className="p-2 rounded bg-white border border-slate-200">
                  <span className="text-[10px] text-slate-400 block">CO₂ Emitted:</span>
                  <span className="font-bold text-slate-800">{selectedVehicle.co2_kg} kg</span>
                </div>

                <div className="p-2 rounded bg-white border border-slate-200">
                  <span className="text-[10px] text-slate-400 block">Current Order:</span>
                  <span className="font-bold text-slate-800">{selectedVehicle.current_order || "None"}</span>
                </div>

                <div className="p-2 rounded bg-white border border-slate-200">
                  <span className="text-[10px] text-slate-400 block">Route Progress:</span>
                  <span className="font-bold text-slate-800">{selectedVehicle.route_progress}% (~{selectedVehicle.eta_mins}m)</span>
                </div>

                <div className="p-2 rounded bg-white border border-slate-200">
                  <span className="text-[10px] text-slate-400 block">Position:</span>
                  <span className="font-bold text-slate-800">{selectedVehicle.x}, {selectedVehicle.y}</span>
                </div>

                <div className="p-2 rounded bg-white border border-slate-200">
                  <span className="text-[10px] text-slate-400 block">Connectivity:</span>
                  <span className="font-bold text-slate-800">{selectedVehicle.connectivity}</span>
                </div>
              </div>

              {selectedVehicle.mesh_neighbors?.length > 0 && (
                <div className="mt-2 p-2 rounded bg-white border border-slate-200 text-[10px] font-mono text-slate-600">
                  <span className="text-slate-400 block">Mesh Neighbors:</span>
                  <span className="font-bold text-slate-800">{selectedVehicle.mesh_neighbors.join(", ")}</span>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
