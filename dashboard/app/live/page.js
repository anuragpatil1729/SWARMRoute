"use client";

import { useState } from "react";
import Section from "../../components/Section";
import Stat from "../../components/Stat";
import OpenStreetMap from "../../components/OpenStreetMap";
import LiveMeshFigure from "../../components/LiveMeshFigure";
import { useDashboardState } from "../../lib/useDashboardState";

export default function LivePage() {
  const {
    state,
    connectionStatus,
    start,
    pause,
    step,
    reset,
    setSpeed,
    breakVehicle,
    toggleCloud,
    injectTraffic,
    injectDemand,
    injectCombined,
  } = useDashboardState();

  const [selectedVehicleId, setSelectedVehicleId] = useState(null);
  const [selectedOrderId, setSelectedOrderId] = useState(null);
  const [targetBreakVehicle, setTargetBreakVehicle] = useState("");
  const [resetDataset, setResetDataset] = useState("C101");
  const [resetCustomers, setResetCustomers] = useState(20);
  const [resetVehicles, setResetVehicles] = useState(4);
  const [resetSeed, setResetSeed] = useState(42);

  // Offline or Waiting State
  if (connectionStatus === "OFFLINE" && !state) {
    return (
      <div className="py-16 text-center">
        <div className="border border-red-200 bg-white rounded-2xl shadow-sm p-8 max-w-lg mx-auto">
          <div className="font-mono text-xs text-red-600 font-bold uppercase tracking-wider">
            Connection Status
          </div>
          <h2 className="text-xl font-bold text-slate-900 mt-2">SIMULATION OFFLINE</h2>
          <p className="text-xs text-slate-500 mt-2 leading-relaxed">
            The live simulation backend at <code className="font-mono bg-slate-100 px-1 py-0.5 rounded text-slate-700">http://127.0.0.1:8000</code> is currently unreachable.
          </p>
          <div className="mt-4 p-3 bg-slate-50 border border-slate-200 rounded-lg text-left font-mono text-xs">
            <span className="text-slate-400"># Start the backend engine in your terminal:</span>
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
          <p className="text-xs text-slate-500 mt-2">Loading live operational telemetry feed...</p>
        </div>
      </div>
    );
  }

  const {
    simulation,
    fleet,
    vehicles,
    orders,
    map: mapData,
    traffic,
    network,
    mesh,
    incidents,
    recovery_flow,
    predictions,
    positioning,
    sustainability,
    performance,
    events,
    timeline,
  } = state;

  const isRunning = simulation.status === "RUNNING";
  const selectedVehicle = vehicles.find((v) => v.id === selectedVehicleId);
  const selectedOrder = orders.find((o) => o.id === selectedOrderId);

  return (
    <div className="space-y-6 w-full">
      {/* 1. Masthead & Control Deck */}
      <div className="border border-slate-200 bg-white rounded-xl shadow-sm p-5">
        <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4 border-b border-slate-100 pb-4">
          <div>
            <div className="flex items-center gap-3">
              <h2 className="text-xl font-bold text-slate-900">
                Fleet Resilience Console
              </h2>
              <span
                className={`font-mono text-[11px] px-2.5 py-0.5 rounded-full font-medium ${
                  connectionStatus === "CONNECTED"
                    ? "text-emerald-700 bg-emerald-50 border border-emerald-200"
                    : "text-red-700 bg-red-50 border border-red-200"
                }`}
              >
                ● {connectionStatus}
              </span>
              <span className="font-mono text-[11px] px-2.5 py-0.5 rounded-full border border-slate-200 text-slate-600 bg-slate-50">
                {simulation.status} · {simulation.time_str}
              </span>
            </div>
            <p className="text-xs text-slate-500 mt-1">
              Live fleet telemetry, OpenStreetMap routing, mesh connectivity, and automated recovery.
            </p>
          </div>

          {/* Primary Simulation Controls */}
          <div className="flex flex-wrap items-center gap-2 font-mono text-xs">
            {isRunning ? (
              <button
                onClick={pause}
                className="px-4 py-1.5 rounded-lg border border-slate-300 bg-white hover:bg-slate-50 text-slate-800 font-semibold shadow-sm transition"
              >
                PAUSE
              </button>
            ) : (
              <button
                onClick={start}
                className="px-4 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-semibold shadow-sm transition"
              >
                START
              </button>
            )}
            <button
              onClick={step}
              disabled={isRunning}
              className={`px-3 py-1.5 rounded-lg border border-slate-200 bg-slate-50 text-slate-700 font-medium ${
                isRunning ? "opacity-40 cursor-not-allowed" : "hover:bg-slate-100 hover:text-slate-900"
              }`}
            >
              STEP (2m)
            </button>
            <button
              onClick={() =>
                reset({
                  dataset: resetDataset,
                  customers: resetCustomers,
                  vehicles: resetVehicles,
                  seed: resetSeed,
                })
              }
              className="px-3 py-1.5 rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-50 hover:text-slate-900"
            >
              RESET
            </button>

            {/* Speed Selector */}
            <div className="flex items-center border border-slate-200 rounded-lg overflow-hidden ml-2 bg-slate-50">
              <span className="px-2 text-[10px] text-slate-400 border-r border-slate-200 font-semibold">SPEED</span>
              {[0.5, 1.0, 2.0, 5.0].map((s) => (
                <button
                  key={s}
                  onClick={() => setSpeed(s)}
                  className={`px-2.5 py-1 text-xs transition ${
                    simulation.speed === s ? "bg-slate-800 text-white font-bold" : "hover:bg-slate-100 text-slate-600"
                  }`}
                >
                  {s}×
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Secondary Bar: Scenario Config & Disruption Injection */}
        <div className="pt-4 grid grid-cols-1 md:grid-cols-2 gap-4 text-xs font-mono">
          {/* Scenario Configuration */}
          <div className="flex flex-wrap items-center gap-3">
            <span className="text-slate-500">Scenario:</span>
            <select
              value={resetDataset}
              onChange={(e) => setResetDataset(e.target.value)}
              disabled={isRunning}
              className="border border-slate-300 rounded-md bg-white px-2 py-1 text-slate-800 focus:outline-none focus:ring-1 focus:ring-blue-500"
            >
              <option value="C101">Solomon C101 (Clustered)</option>
              <option value="R101">Solomon R101 (Random)</option>
              <option value="RC101">Solomon RC101 (Mixed)</option>
            </select>
            <label className="flex items-center gap-1 text-slate-500">
              Fleet:
              <input
                type="number"
                min="2"
                max="25"
                value={resetVehicles}
                onChange={(e) => setResetVehicles(parseInt(e.target.value) || 4)}
                disabled={isRunning}
                className="w-12 border border-slate-300 rounded-md bg-white px-1.5 py-0.5 text-slate-800"
              />
            </label>
            <label className="flex items-center gap-1 text-slate-500">
              Orders:
              <input
                type="number"
                min="5"
                max="50"
                value={resetCustomers}
                onChange={(e) => setResetCustomers(parseInt(e.target.value) || 20)}
                disabled={isRunning}
                className="w-12 border border-slate-300 rounded-md bg-white px-1.5 py-0.5 text-slate-800"
              />
            </label>
            <label className="flex items-center gap-1 text-slate-500">
              Seed:
              <input
                type="number"
                value={resetSeed}
                onChange={(e) => setResetSeed(parseInt(e.target.value) || 42)}
                disabled={isRunning}
                className="w-14 border border-slate-300 rounded-md bg-white px-1.5 py-0.5 text-slate-800"
              />
            </label>
          </div>

          {/* Real Disruption Injectors */}
          <div className="flex flex-wrap items-center justify-start md:justify-end gap-2">
            <span className="text-red-600 font-semibold text-[11px]">Inject:</span>
            <div className="flex items-center border border-red-300 rounded-md overflow-hidden">
              <select
                value={targetBreakVehicle}
                onChange={(e) => setTargetBreakVehicle(e.target.value)}
                className="bg-white text-slate-800 px-2 py-1 text-[11px] border-r border-red-300 focus:outline-none"
              >
                <option value="">Auto Select</option>
                {vehicles.map((v) => (
                  <option key={v.id} value={v.id}>
                    {v.id}
                  </option>
                ))}
              </select>
              <button
                onClick={() => breakVehicle(targetBreakVehicle || null)}
                className="px-2.5 py-1 bg-red-600 text-white hover:bg-red-700 font-semibold text-[11px] transition"
              >
                BREAK TRUCK
              </button>
            </div>
            <button
              onClick={() => toggleCloud()}
              className="px-2.5 py-1 rounded-md border border-slate-300 bg-white hover:bg-slate-50 text-slate-700 font-medium text-[11px] transition"
            >
              {network.mode === "CLOUD_MODE" ? "DISABLE CLOUD" : "RESTORE CLOUD"}
            </button>
            <button
              onClick={() => injectTraffic()}
              className="px-2.5 py-1 rounded-md border border-slate-200 bg-slate-50 hover:bg-slate-100 text-slate-700 font-medium text-[11px] transition"
            >
              SPIKE TRAFFIC
            </button>
            <button
              onClick={() => injectDemand()}
              className="px-2.5 py-1 rounded-md border border-slate-200 bg-slate-50 hover:bg-slate-100 text-slate-700 font-medium text-[11px] transition"
            >
              DEMAND BURST
            </button>
          </div>
        </div>
      </div>

      {/* 2. Sustainability & Delivery KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        <Stat
          label="success rate"
          value={performance.success_rate}
          unit="%"
          sub={`${performance.delivered} / ${performance.total_orders} delivered`}
        />
        <Stat
          label="on-time rate"
          value={performance.on_time_rate}
          unit="%"
          sub={`${performance.late} late · ${performance.failed} failed`}
        />
        <Stat
          label="distance"
          value={sustainability.total_distance_km}
          unit="km"
          sub={`${sustainability.empty_km} km empty`}
        />
        <Stat
          label="fuel consumed"
          value={sustainability.fuel_liters}
          unit="L"
          sub={`${sustainability.fuel_per_delivery} L / delivery`}
        />
        <Stat
          label="CO2 emissions"
          value={sustainability.co2_kg}
          unit="kg"
          sub="2.68 kg CO2 / L"
        />
        <Stat
          label="fleet active"
          value={`${fleet.active} / ${fleet.size}`}
          unit=""
          sub={`${fleet.broken} broken · ${fleet.utilization_pct}% util`}
        />
      </div>

      {/* 3. Live Operational Map & Mesh Topology */}
      <div className="grid grid-cols-1 lg:grid-cols-[1fr_340px] gap-6">
        <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm space-y-3">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-base font-bold text-slate-900">
                Live OpenStreetMap Fleet Routing
              </h3>
              <p className="text-xs text-slate-500">
                Real-time OpenStreetMap GIS tracking with multi-agent routing and automated peer recovery.
              </p>
            </div>
            <span className="font-mono text-xs text-slate-500 bg-slate-50 px-2.5 py-1 rounded-md border border-slate-200">
              {simulation.dataset} · Depot (40, 50)
            </span>
          </div>

          <OpenStreetMap
            customers={mapData.customers}
            depot={mapData.depot}
            routes={mapData.active_routes}
            recoveryRoutes={mapData.recovery_routes}
            vehicles={vehicles}
            trafficEdges={mapData.traffic_edges}
            selectedVehicleId={selectedVehicleId}
            onSelectVehicle={(id) => setSelectedVehicleId(id)}
            onSelectOrder={(id) => setSelectedOrderId(id)}
          />

          <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-slate-500 pt-1 font-mono">
            <span>Click any truck marker or delivery stop to inspect live telemetry.</span>
            <span>Real-time coordinates synced with simulation engine.</span>
          </div>
        </div>

        {/* Network & Mesh Panel */}
        <div className="space-y-4">
          <div className="border border-slate-200 bg-white rounded-xl shadow-sm p-4 space-y-3">
            <div className="flex items-center justify-between border-b border-slate-100 pb-2">
              <span className="font-mono text-xs font-semibold text-slate-700">Network Topology</span>
              <span
                className={`font-mono text-[11px] px-2 py-0.5 rounded-full font-medium ${
                  network.mode === "CLOUD_MODE"
                    ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                    : "bg-amber-50 text-amber-700 border border-amber-200"
                }`}
              >
                {network.mode}
              </span>
            </div>

            <div className="h-[150px] border border-slate-100 bg-slate-50 rounded-lg p-2">
              <LiveMeshFigure
                mesh={mesh}
                activeRecovery={
                  incidents.length > 0
                    ? { broken: incidents[0].vehicle_id, winner: incidents[0].recovery_vehicle }
                    : null
                }
              />
            </div>

            <dl className="font-mono text-xs space-y-1.5 divide-y divide-slate-100 pt-1">
              <div className="flex justify-between pt-1">
                <dt className="text-slate-500">Mesh links</dt>
                <dd className="text-slate-800 font-semibold">{mesh.links.length} active (≤30km)</dd>
              </div>
              <div className="flex justify-between pt-1">
                <dt className="text-slate-500">Mesh messages</dt>
                <dd className="text-slate-800 font-semibold">{network.messages_sent} transmitted</dd>
              </div>
              <div className="flex justify-between pt-1">
                <dt className="text-slate-500">Avg hop latency</dt>
                <dd className="text-slate-800 font-semibold">{network.avg_latency_ms} ms</dd>
              </div>
              <div className="flex justify-between pt-1">
                <dt className="text-slate-500">Mesh components</dt>
                <dd className="text-slate-800 font-semibold">{network.connected_components}</dd>
              </div>
            </dl>
          </div>

          {/* Traffic Alert Box */}
          <div className="border border-slate-200 bg-white rounded-xl shadow-sm p-4">
            <div className="flex items-center justify-between border-b border-slate-100 pb-2">
              <span className="font-mono text-xs font-semibold text-slate-700">Traffic Dynamics</span>
              <span
                className={`font-mono text-[11px] font-semibold px-2 py-0.5 rounded-full ${
                  traffic.congestion_level === "SEVERE"
                    ? "bg-red-50 text-red-600 border border-red-200"
                    : "bg-emerald-50 text-emerald-600 border border-emerald-200"
                }`}
              >
                {traffic.congestion_level}
              </span>
            </div>
            <div className="mt-2 text-xs space-y-1.5 font-mono">
              <div className="flex justify-between">
                <span className="text-slate-500">Avg fleet speed:</span>
                <span className="text-slate-800 font-semibold">{traffic.average_speed} km/h</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Congested segments:</span>
                <span className="text-slate-800 font-semibold">{traffic.affected_roads.length} link(s)</span>
              </div>
              {traffic.affected_roads.map((r, i) => (
                <div key={i} className="text-[11px] text-red-600 pt-1 border-t border-slate-100">
                  Road ({r.u} → {r.v}): {r.level} ({r.speed} km/h)
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* 4. Active Incidents & Self-Healing Pipeline */}
      <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm space-y-4">
        <div className="flex items-center justify-between border-b border-slate-100 pb-3">
          <h3 className="text-base font-bold text-slate-900">
            Breakdown Monitoring & Decentralized Self-Healing
          </h3>
          <span className="text-xs font-mono text-slate-500">
            {incidents.length === 0 ? "Fleet Status: Normal" : "Recovery Active"}
          </span>
        </div>

        {incidents.length === 0 ? (
          <div className="border border-slate-100 bg-slate-50 rounded-lg p-6 text-center font-mono text-xs text-slate-500">
            NO ACTIVE INCIDENTS · All {fleet.size} fleet vehicles operational
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-[280px_1fr] gap-4">
            {/* Incident Summary Card */}
            <div className="border border-red-200 bg-red-50/40 rounded-lg p-4 text-xs font-mono space-y-2">
              <div className="text-red-700 font-bold uppercase tracking-wider text-[11px]">
                Incident #{incidents[0].id}
              </div>
              <div className="text-sm text-slate-900 font-bold">
                Vehicle {incidents[0].vehicle_id} Failed
              </div>
              <div className="divide-y divide-red-100 space-y-1.5 pt-1">
                <div className="flex justify-between pt-1">
                  <span className="text-slate-500">Fault time:</span>
                  <span className="text-slate-800">{incidents[0].time_str}</span>
                </div>
                <div className="flex justify-between pt-1">
                  <span className="text-slate-500">Recovery unit:</span>
                  <span className="text-slate-900 font-bold">{incidents[0].recovery_vehicle}</span>
                </div>
                <div className="flex justify-between pt-1">
                  <span className="text-slate-500">Auction time:</span>
                  <span className="text-emerald-700 font-bold">
                    {(incidents[0].recovery_time_sec * 1000).toFixed(1)} ms
                  </span>
                </div>
                <div className="flex justify-between pt-1">
                  <span className="text-slate-500">Stranded orders:</span>
                  <span className="text-slate-800">{incidents[0].stranded_orders.join(", ")}</span>
                </div>
                <div className="flex justify-between pt-1">
                  <span className="text-slate-500">Detour:</span>
                  <span className="text-slate-800">+{incidents[0].recovery_distance_km} km</span>
                </div>
                <div className="flex justify-between pt-1">
                  <span className="text-slate-500">Extra fuel / CO2:</span>
                  <span className="text-slate-800">
                    +{incidents[0].recovery_fuel_l} L ({incidents[0].recovery_co2_kg} kg)
                  </span>
                </div>
              </div>
            </div>

            {/* Self-Healing Stepper */}
            <div className="border border-slate-200 bg-white rounded-lg p-4">
              <div className="font-mono text-xs text-slate-500 mb-3">
                Peer-to-Peer Contract-Net Auction Pipeline
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2 text-center font-mono text-[11px]">
                {recovery_flow.map((step, idx) => (
                  <div
                    key={step.id}
                    className="p-2.5 rounded-lg border border-slate-200 bg-slate-50/50 flex flex-col justify-between"
                  >
                    <div>
                      <span className="text-[10px] text-blue-600 font-bold block mb-1">0{idx + 1}</span>
                      <span className="font-semibold text-slate-800 block leading-snug">
                        {step.title}
                      </span>
                    </div>
                    <span className="text-[10px] text-slate-500 mt-2 block border-t border-slate-200 pt-1">
                      {step.detail}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* 5. Live Fleet Overview & Vehicle Inspector */}
      <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm space-y-4">
        <div className="flex items-center justify-between border-b border-slate-100 pb-3">
          <div>
            <h3 className="text-base font-bold text-slate-900">
              Live Fleet Overview
            </h3>
            <p className="text-xs text-slate-500">
              Operational status, real-time telemetry, battery/fuel, and assigned tour routes.
            </p>
          </div>
          <span className="text-xs font-mono text-slate-500 bg-slate-50 px-2.5 py-1 rounded-md border border-slate-200">
            {vehicles.length} Vehicles
          </span>
        </div>

        <div className="border border-slate-200 rounded-lg overflow-x-auto">
          <table className="w-full text-xs font-mono">
            <thead>
              <tr className="text-left border-b border-slate-200 bg-slate-50 text-slate-500 font-semibold">
                <th className="px-3 py-2.5">Vehicle</th>
                <th className="px-3 py-2.5">Status</th>
                <th className="px-3 py-2.5">Position</th>
                <th className="px-3 py-2.5">Speed</th>
                <th className="px-3 py-2.5">Progress</th>
                <th className="px-3 py-2.5">Load / Cap</th>
                <th className="px-3 py-2.5">Fuel Left</th>
                <th className="px-3 py-2.5">CO2</th>
                <th className="px-3 py-2.5">Neighbors</th>
                <th className="px-3 py-2.5">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 bg-white">
              {vehicles.map((v, i) => {
                const isSelected = selectedVehicleId === v.id;
                const isBroken = v.status === "BROKEN_DOWN";
                return (
                  <tr
                    key={v.id}
                    onClick={() => setSelectedVehicleId(isSelected ? null : v.id)}
                    className={`cursor-pointer transition-colors ${
                      isSelected
                        ? "bg-blue-50/70"
                        : isBroken
                        ? "bg-red-50/60"
                        : i % 2 === 1
                        ? "bg-slate-50/40"
                        : ""
                    } hover:bg-slate-100/70`}
                  >
                    <td className="px-3 py-2.5 font-bold text-slate-900">{v.id}</td>
                    <td className="px-3 py-2.5">
                      <span
                        className={`px-2 py-0.5 rounded-full text-[10px] font-semibold border ${
                          isBroken
                            ? "border-red-200 bg-red-50 text-red-700"
                            : v.status === "EN_ROUTE"
                            ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                            : "border-slate-200 bg-slate-50 text-slate-600"
                        }`}
                      >
                        {v.status}
                      </span>
                    </td>
                    <td className="px-3 py-2.5 text-slate-500">
                      ({v.x.toFixed(1)}, {v.y.toFixed(1)})
                    </td>
                    <td className="px-3 py-2.5 text-slate-800">{v.speed_kmh} km/h</td>
                    <td className="px-3 py-2.5">
                      <div className="flex items-center gap-2">
                        <div className="w-14 h-1.5 bg-slate-100 rounded-full overflow-hidden border border-slate-200">
                          <div
                            className="h-full bg-blue-600 rounded-full"
                            style={{ width: `${v.route_progress}%` }}
                          />
                        </div>
                        <span className="text-slate-700">{v.route_progress}%</span>
                      </div>
                    </td>
                    <td className="px-3 py-2.5 text-slate-800">
                      {v.current_load} / {v.max_weight} kg
                    </td>
                    <td className="px-3 py-2.5 text-slate-800">{v.fuel_level} L</td>
                    <td className="px-3 py-2.5 text-slate-800">{v.co2_kg} kg</td>
                    <td className="px-3 py-2.5 text-slate-500">
                      {v.mesh_neighbors.length > 0 ? v.mesh_neighbors.join(", ") : "—"}
                    </td>
                    <td className="px-3 py-2.5 text-slate-900 font-semibold">{v.last_action}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {/* Selected Vehicle Inspector Drawer */}
        {selectedVehicle && (
          <div className="mt-4 border border-blue-200 bg-blue-50/30 rounded-xl p-4 text-xs font-mono">
            <div className="flex items-center justify-between border-b border-blue-200 pb-2">
              <span className="text-sm text-slate-900 font-bold">
                Vehicle Inspector — {selectedVehicle.id}
              </span>
              <button
                onClick={() => setSelectedVehicleId(null)}
                className="text-slate-400 hover:text-slate-800"
              >
                ✕ close
              </button>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 pt-3">
              <div>
                <span className="text-slate-500 block">Current Road Edge:</span>
                <span className="text-slate-900 font-semibold">{selectedVehicle.edge}</span>
              </div>
              <div>
                <span className="text-slate-500 block">Assigned Tour:</span>
                <span className="text-slate-900">
                  {selectedVehicle.current_route.join(" → ") || "None"}
                </span>
              </div>
              <div>
                <span className="text-slate-500 block">Assigned Orders:</span>
                <span className="text-slate-900">
                  {selectedVehicle.assigned_orders.join(", ") || "None"}
                </span>
              </div>
              <div>
                <span className="text-slate-500 block">ETA to Finish:</span>
                <span className="text-slate-900 font-semibold">+{selectedVehicle.eta_mins} mins</span>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* 6. Live Order Table & Predictive Demand */}
      <div className="grid grid-cols-1 lg:grid-cols-[1fr_360px] gap-6">
        {/* Order Monitoring */}
        <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm space-y-4">
          <div className="flex items-center justify-between border-b border-slate-100 pb-3">
            <h3 className="text-base font-bold text-slate-900">
              Order Monitoring & Dispatch Status
            </h3>
            <span className="text-xs font-mono text-slate-500">
              {orders.length} Total Orders
            </span>
          </div>

          <div className="border border-slate-200 rounded-lg overflow-x-auto max-h-80 overflow-y-auto">
            <table className="w-full text-xs font-mono">
              <thead className="sticky top-0 bg-slate-50 border-b border-slate-200 text-slate-500 font-semibold">
                <tr className="text-left">
                  <th className="px-3 py-2">Order ID</th>
                  <th className="px-3 py-2">Customer</th>
                  <th className="px-3 py-2">Assigned Truck</th>
                  <th className="px-3 py-2">Status</th>
                  <th className="px-3 py-2">Demand</th>
                  <th className="px-3 py-2">Deadline</th>
                  <th className="px-3 py-2">ETA</th>
                  <th className="px-3 py-2">Delay</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 bg-white">
                {orders.map((o, i) => {
                  const isSelected = selectedOrderId === o.id;
                  const isDelivered = o.status === "DELIVERED";
                  const isLate = o.status === "LATE";
                  return (
                    <tr
                      key={o.id}
                      onClick={() => setSelectedOrderId(isSelected ? null : o.id)}
                      className={`cursor-pointer transition-colors ${
                        isSelected ? "bg-blue-50/70" : i % 2 === 1 ? "bg-slate-50/40" : ""
                      } hover:bg-slate-100/70`}
                    >
                      <td className="px-3 py-2 font-bold text-slate-900">{o.id}</td>
                      <td className="px-3 py-2 text-slate-600">Customer #{o.customer_id}</td>
                      <td className="px-3 py-2 text-slate-600">{o.assigned_vehicle || "UNASSIGNED"}</td>
                      <td className="px-3 py-2">
                        <span
                          className={`px-2 py-0.5 rounded-full text-[10px] font-semibold border ${
                            isDelivered
                              ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                              : isLate
                              ? "border-red-200 bg-red-50 text-red-700"
                              : "border-slate-200 bg-slate-50 text-slate-600"
                          }`}
                        >
                          {o.status}
                        </span>
                      </td>
                      <td className="px-3 py-2 text-slate-800">{o.demand} kg</td>
                      <td className="px-3 py-2 text-slate-800">{o.deadline}m</td>
                      <td className="px-3 py-2 text-slate-800">{o.eta}m</td>
                      <td className="px-3 py-2">
                        {o.delay > 0 ? (
                          <span className="text-red-600 font-semibold">+{o.delay}m</span>
                        ) : (
                          "—"
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {selectedOrder && (
            <div className="mt-3 border border-blue-200 bg-blue-50/30 rounded-xl p-3 text-xs font-mono">
              <div className="flex justify-between border-b border-blue-200 pb-1.5">
                <span className="font-bold text-slate-900">
                  Order Details: {selectedOrder.id}
                </span>
                <button onClick={() => setSelectedOrderId(null)} className="text-slate-400 hover:text-slate-700">
                  ✕
                </button>
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-2 text-slate-700">
                <div>Coordinates: ({selectedOrder.x.toFixed(1)}, {selectedOrder.y.toFixed(1)})</div>
                <div>Time Window: [{selectedOrder.ready_time}m, {selectedOrder.deadline}m]</div>
                <div>Remaining Distance: {selectedOrder.distance_remaining} km</div>
                <div>Delivery Status: <span className="font-bold">{selectedOrder.status}</span></div>
              </div>
            </div>
          )}
        </div>

        {/* Spatial Demand Forecasting & Positioning */}
        <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm space-y-4">
          <div className="flex items-center justify-between border-b border-slate-100 pb-3">
            <h3 className="text-base font-bold text-slate-900">
              Spatial Demand Forecasting
            </h3>
            <span className="text-xs font-mono text-slate-500 bg-slate-50 px-2 py-0.5 rounded border border-slate-200">
              Zone Modeling
            </span>
          </div>

          <table className="w-full text-xs font-mono">
            <thead>
              <tr className="text-left border-b border-slate-200 bg-slate-50 text-slate-500 font-semibold">
                <th className="px-2.5 py-1.5">Zone</th>
                <th className="px-2.5 py-1.5">Predicted</th>
                <th className="px-2.5 py-1.5">Actual</th>
                <th className="px-2.5 py-1.5">Diff</th>
                <th className="px-2.5 py-1.5">Trend</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 bg-white">
              {predictions.zones.map((z, idx) => (
                <tr key={idx}>
                  <td className="px-2.5 py-1.5 font-semibold text-slate-900">{z.zone}</td>
                  <td className="px-2.5 py-1.5 text-slate-800">{z.predicted_demand} /hr</td>
                  <td className="px-2.5 py-1.5 text-slate-500">{z.actual_demand} /hr</td>
                  <td className="px-2.5 py-1.5 text-slate-800">{z.diff}</td>
                  <td className="px-2.5 py-1.5 text-blue-600 font-semibold">{z.trend}</td>
                </tr>
              ))}
            </tbody>
          </table>

          {positioning.length > 0 && (
            <div className="p-3 rounded-lg border border-emerald-200 bg-emerald-50/40 text-xs font-mono">
              <span className="text-emerald-800 font-bold block">
                Proactive Repositioning Active:
              </span>
              <div className="mt-1 text-slate-600 text-[11px]">
                {positioning[0].vehicle_id} relocating ({positioning[0].current_zone} → {positioning[0].target_zone}) to absorb forecasted demand spike.
              </div>
            </div>
          )}
        </div>
      </div>

      {/* 7. Live Chronological Event Log & Timeline */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Live Event Log Feed */}
        <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm space-y-3">
          <div className="flex items-center justify-between border-b border-slate-100 pb-2">
            <h3 className="text-base font-bold text-slate-900">Live Event Feed</h3>
            <span className="font-mono text-xs text-slate-400">{events.length} events</span>
          </div>
          <div className="max-h-72 overflow-y-auto divide-y divide-slate-100 font-mono text-xs">
            {events.length === 0 ? (
              <div className="p-4 text-center text-slate-400">No events recorded.</div>
            ) : (
              events.map((ev) => (
                <div key={ev.id} className="p-2.5 flex items-start gap-3 hover:bg-slate-50 transition">
                  <span className="text-slate-400 shrink-0 text-[11px] pt-0.5">{ev.time_str}</span>
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <span
                        className={`text-[10px] px-1.5 py-0.5 rounded font-semibold border ${
                          ev.severity === "DANGER"
                            ? "border-red-200 bg-red-50 text-red-600"
                            : ev.severity === "WARNING"
                            ? "border-amber-200 bg-amber-50 text-amber-600"
                            : ev.severity === "SUCCESS"
                            ? "border-emerald-200 bg-emerald-50 text-emerald-600"
                            : "border-slate-200 bg-slate-50 text-slate-500"
                        }`}
                      >
                        {ev.type}
                      </span>
                      <span className="text-slate-900 font-semibold">{ev.target}</span>
                    </div>
                    <p className="text-slate-600 text-[11px] mt-0.5 leading-snug">
                      {ev.description}
                    </p>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Milestone Timeline */}
        <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm space-y-3">
          <div className="flex items-center justify-between border-b border-slate-100 pb-2">
            <h3 className="text-base font-bold text-slate-900">Operational Milestones</h3>
            <span className="font-mono text-xs text-slate-400">{timeline.length} milestones</span>
          </div>
          <div className="p-2 max-h-72 overflow-y-auto">
            <ol className="relative border-l border-slate-200 ml-3 space-y-4 font-mono text-xs">
              {timeline.map((t, idx) => (
                <li key={idx} className="ml-4">
                  <div className="absolute -left-1.5 mt-1 w-3 h-3 rounded-full border-2 border-white bg-blue-600 shadow-sm" />
                  <span className="text-[10px] text-slate-400 block">{t.time_str}</span>
                  <span className="text-slate-900 font-semibold text-xs block">{t.title}</span>
                  <span className="text-slate-500 text-[11px] leading-snug">{t.description}</span>
                </li>
              ))}
            </ol>
          </div>
        </div>
      </div>
    </div>
  );
}
