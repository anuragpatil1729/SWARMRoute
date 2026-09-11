"use client";

import { useState } from "react";
import Section from "../../components/Section";
import Stat from "../../components/Stat";
import LiveRouteMap from "../../components/LiveRouteMap";
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
      <div className="py-12 text-center">
        <div className="border border-red bg-panel p-8 max-w-lg mx-auto">
          <div className="mono text-xs text-red font-bold uppercase tracking-wider">
            Connection Error
          </div>
          <h2 className="serif text-xl text-ink mt-2">SIMULATION OFFLINE</h2>
          <p className="text-xs text-muted mt-2 leading-relaxed">
            The live simulation backend at <code className="mono bg-panel2 px-1">http://127.0.0.1:8000</code> is currently unreachable.
          </p>
          <div className="mt-4 p-3 bg-panel2 border border-rule text-left mono text-xs">
            <span className="text-muted"># Start the backend engine in your terminal:</span>
            <br />
            <span className="text-ink font-semibold">python scripts/run_dashboard_backend.py</span>
          </div>
        </div>
      </div>
    );
  }

  if (!state) {
    return (
      <div className="py-12 text-center">
        <div className="border border-ink bg-panel p-8 max-w-md mx-auto">
          <div className="mono text-xs text-muted">status</div>
          <h2 className="serif text-xl text-ink mt-1">WAITING FOR SIMULATION</h2>
          <p className="text-xs text-muted mt-2">Connecting to live telemetry feed...</p>
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
    ppo,
    sustainability,
    performance,
    events,
    timeline,
  } = state;

  const isRunning = simulation.status === "RUNNING";
  const selectedVehicle = vehicles.find((v) => v.id === selectedVehicleId);
  const selectedOrder = orders.find((o) => o.id === selectedOrderId);

  return (
    <div className="space-y-8">
      {/* 1. Masthead & Control Deck */}
      <div className="border border-ink bg-panel p-5">
        <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4 border-b border-rule pb-4">
          <div>
            <div className="flex items-center gap-3">
              <h2 className="serif text-xl text-ink font-normal">
                Fleet Resilience Console
              </h2>
              <span
                className={`mono text-[11px] px-2 py-0.5 border ${
                  connectionStatus === "CONNECTED"
                    ? "border-green text-green bg-[#edf4ec]"
                    : "border-red text-red bg-[#faecea]"
                }`}
              >
                ● {connectionStatus}
              </span>
              <span className="mono text-[11px] px-2 py-0.5 border border-rule text-muted">
                {simulation.status} · {simulation.time_str}
              </span>
            </div>
            <p className="text-xs text-muted mt-1">
              Real-time telemetry, RF mesh networking, discrete physics movement, and PPO decision streams.
            </p>
          </div>

          {/* Primary Simulation Controls */}
          <div className="flex flex-wrap items-center gap-2 mono text-xs">
            {isRunning ? (
              <button
                onClick={pause}
                className="px-3 py-1.5 border border-ink bg-panel2 hover:bg-paper text-ink font-semibold"
              >
                PAUSE
              </button>
            ) : (
              <button
                onClick={start}
                className="px-3 py-1.5 border border-green bg-green text-panel font-semibold hover:opacity-90"
              >
                START
              </button>
            )}
            <button
              onClick={step}
              disabled={isRunning}
              className={`px-3 py-1.5 border border-ink bg-panel2 text-ink ${
                isRunning ? "opacity-40 cursor-not-allowed" : "hover:bg-paper"
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
              className="px-3 py-1.5 border border-rule text-muted hover:border-ink hover:text-ink"
            >
              RESET
            </button>

            {/* Speed Selector */}
            <div className="flex items-center border border-rule ml-2">
              <span className="px-2 text-[10px] text-muted border-r border-rule">SPEED</span>
              {[0.5, 1.0, 2.0, 5.0].map((s) => (
                <button
                  key={s}
                  onClick={() => setSpeed(s)}
                  className={`px-2 py-1 text-xs ${
                    simulation.speed === s ? "bg-ink text-panel" : "hover:bg-panel2 text-ink"
                  }`}
                >
                  {s}×
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Secondary Bar: Scenario Config & Disruption Injection */}
        <div className="pt-4 grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
          {/* Scenario Configuration */}
          <div className="flex flex-wrap items-center gap-3 mono">
            <span className="text-muted">Scenario:</span>
            <select
              value={resetDataset}
              onChange={(e) => setResetDataset(e.target.value)}
              disabled={isRunning}
              className="border border-rule bg-paper px-2 py-1 text-ink"
            >
              <option value="C101">Solomon C101 (Clustered)</option>
              <option value="R101">Solomon R101 (Random)</option>
              <option value="RC101">Solomon RC101 (Mixed)</option>
            </select>
            <label className="flex items-center gap-1 text-muted">
              Fleet:
              <input
                type="number"
                min="2"
                max="25"
                value={resetVehicles}
                onChange={(e) => setResetVehicles(parseInt(e.target.value) || 4)}
                disabled={isRunning}
                className="w-12 border border-rule bg-paper px-1.5 py-0.5 text-ink"
              />
            </label>
            <label className="flex items-center gap-1 text-muted">
              Orders:
              <input
                type="number"
                min="5"
                max="50"
                value={resetCustomers}
                onChange={(e) => setResetCustomers(parseInt(e.target.value) || 20)}
                disabled={isRunning}
                className="w-12 border border-rule bg-paper px-1.5 py-0.5 text-ink"
              />
            </label>
            <label className="flex items-center gap-1 text-muted">
              Seed:
              <input
                type="number"
                value={resetSeed}
                onChange={(e) => setResetSeed(parseInt(e.target.value) || 42)}
                disabled={isRunning}
                className="w-14 border border-rule bg-paper px-1.5 py-0.5 text-ink"
              />
            </label>
          </div>

          {/* Real Disruption Injectors */}
          <div className="flex flex-wrap items-center justify-start md:justify-end gap-2 mono">
            <span className="text-red font-semibold">Inject:</span>
            <div className="flex items-center border border-red">
              <select
                value={targetBreakVehicle}
                onChange={(e) => setTargetBreakVehicle(e.target.value)}
                className="bg-paper text-ink px-1.5 py-1 text-[11px] border-r border-red"
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
                className="px-2.5 py-1 bg-red text-panel hover:opacity-90 font-semibold"
              >
                BREAK TRUCK
              </button>
            </div>
            <button
              onClick={() => toggleCloud()}
              className="px-2 py-1 border border-ink bg-panel2 hover:bg-paper"
            >
              {network.mode === "CLOUD_MODE" ? "DISABLE CLOUD" : "RESTORE CLOUD"}
            </button>
            <button
              onClick={() => injectTraffic()}
              className="px-2 py-1 border border-rule hover:border-ink"
            >
              SPIKE TRAFFIC
            </button>
            <button
              onClick={() => injectDemand()}
              className="px-2 py-1 border border-rule hover:border-ink"
            >
              DEMAND BURST
            </button>
          </div>
        </div>
      </div>

      {/* 2. Sustainability & Delivery KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
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
      <div className="grid grid-cols-1 lg:grid-cols-[1fr_320px] gap-6">
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <h3 className="serif text-base text-ink">Figure 1 — Operational Live Map</h3>
            <span className="mono text-xs text-muted">
              Solomon {simulation.dataset} · Depot (40, 50)
            </span>
          </div>
          <LiveRouteMap
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
          <p className="text-xs text-muted">
            Continuous discrete edge tracking. Red markers indicate vehicle faults; dashed amber lines represent active peer recovery detours.
          </p>
        </div>

        {/* Network & RF Mesh Panel */}
        <div className="space-y-4">
          <div className="border border-ink bg-panel p-4 space-y-3">
            <div className="flex items-center justify-between border-b border-rule pb-2">
              <span className="mono text-xs text-muted">network topology</span>
              <span
                className={`mono text-[11px] px-2 py-0.5 border ${
                  network.mode === "CLOUD_MODE"
                    ? "border-green text-green"
                    : "border-amber text-amber font-semibold"
                }`}
              >
                {network.mode}
              </span>
            </div>

            <div className="h-[150px] border border-rule bg-paper p-2">
              <LiveMeshFigure
                mesh={mesh}
                activeRecovery={
                  incidents.length > 0
                    ? { broken: incidents[0].vehicle_id, winner: incidents[0].recovery_vehicle }
                    : null
                }
              />
            </div>

            <dl className="mono text-xs space-y-1.5 divide-y divide-rule pt-1">
              <div className="flex justify-between pt-1">
                <dt className="text-muted">mesh links</dt>
                <dd className="text-ink">{mesh.links.length} active (≤30km)</dd>
              </div>
              <div className="flex justify-between pt-1">
                <dt className="text-muted">mesh messages</dt>
                <dd className="text-ink">{network.messages_sent} transmitted</dd>
              </div>
              <div className="flex justify-between pt-1">
                <dt className="text-muted">avg hop latency</dt>
                <dd className="text-ink">{network.avg_latency_ms} ms</dd>
              </div>
              <div className="flex justify-between pt-1">
                <dt className="text-muted">mesh components</dt>
                <dd className="text-ink">{network.connected_components}</dd>
              </div>
            </dl>
          </div>

          {/* Traffic Alert Box */}
          <div className="border border-ink bg-panel p-4">
            <div className="flex items-center justify-between border-b border-rule pb-2">
              <span className="mono text-xs text-muted">traffic dynamics</span>
              <span
                className={`mono text-[11px] font-semibold ${
                  traffic.congestion_level === "SEVERE" ? "text-red" : "text-green"
                }`}
              >
                {traffic.congestion_level}
              </span>
            </div>
            <div className="mt-2 text-xs space-y-1 mono">
              <div className="flex justify-between">
                <span className="text-muted">avg fleet speed:</span>
                <span className="text-ink">{traffic.average_speed} km/h</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted">affected links:</span>
                <span className="text-ink">{traffic.affected_roads.length} segment(s)</span>
              </div>
              {traffic.affected_roads.map((r, i) => (
                <div key={i} className="text-[11px] text-red pt-1 border-t border-rule">
                  Edge ({r.u} → {r.v}): {r.level} Congestion ({r.speed} km/h)
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* 4. Active Incidents & Self-Healing Pipeline */}
      <Section index="2" title="Breakdown Monitoring & Decentralized Self-Healing">
        {incidents.length === 0 ? (
          <div className="border border-rule bg-panel p-6 text-center mono text-xs text-muted">
            NO ACTIVE INCIDENTS · All {fleet.size} fleet vehicles operational
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-[280px_1fr] gap-6">
            {/* Incident Summary Card */}
            <div className="border border-red bg-panel p-4 text-xs mono space-y-2">
              <div className="text-red font-bold uppercase tracking-wider">
                Incident #{incidents[0].id}
              </div>
              <div className="serif text-base text-ink font-semibold">
                Vehicle {incidents[0].vehicle_id} Failed
              </div>
              <div className="divide-y divide-rule space-y-1.5 pt-1">
                <div className="flex justify-between pt-1">
                  <span className="text-muted">fault time:</span>
                  <span className="text-ink">{incidents[0].time_str}</span>
                </div>
                <div className="flex justify-between pt-1">
                  <span className="text-muted">recovery vehicle:</span>
                  <span className="text-ink font-bold">{incidents[0].recovery_vehicle}</span>
                </div>
                <div className="flex justify-between pt-1">
                  <span className="text-muted">auction time:</span>
                  <span className="text-green font-bold">
                    {(incidents[0].recovery_time_sec * 1000).toFixed(1)} ms
                  </span>
                </div>
                <div className="flex justify-between pt-1">
                  <span className="text-muted">stranded orders:</span>
                  <span className="text-ink">{incidents[0].stranded_orders.join(", ")}</span>
                </div>
                <div className="flex justify-between pt-1">
                  <span className="text-muted">recovery detour:</span>
                  <span className="text-ink">+{incidents[0].recovery_distance_km} km</span>
                </div>
                <div className="flex justify-between pt-1">
                  <span className="text-muted">extra fuel / CO2:</span>
                  <span className="text-ink">
                    +{incidents[0].recovery_fuel_l} L ({incidents[0].recovery_co2_kg} kg)
                  </span>
                </div>
              </div>
            </div>

            {/* Self-Healing Stepper */}
            <div className="border border-ink bg-panel p-4">
              <div className="mono text-xs text-muted mb-3">
                contract-net peer-to-peer auction pipeline
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2 text-center mono text-[11px]">
                {recovery_flow.map((step, idx) => (
                  <div
                    key={step.id}
                    className="p-2 border border-rule bg-paper flex flex-col justify-between"
                  >
                    <div>
                      <span className="text-[10px] text-muted block mb-1">0{idx + 1}</span>
                      <span className="font-semibold text-ink block leading-snug">
                        {step.title}
                      </span>
                    </div>
                    <span className="text-[10px] text-muted mt-2 block border-t border-rule pt-1">
                      {step.detail}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </Section>

      {/* 5. Live Fleet Overview & Vehicle Inspector */}
      <Section index="3" title="Live Fleet Overview">
        <div className="border border-ink overflow-x-auto">
          <table className="w-full text-xs mono">
            <thead>
              <tr className="text-left border-b border-ink bg-panel2">
                <th className="px-3 py-2 text-muted font-normal">vehicle</th>
                <th className="px-3 py-2 text-muted font-normal">status</th>
                <th className="px-3 py-2 text-muted font-normal">position</th>
                <th className="px-3 py-2 text-muted font-normal">speed</th>
                <th className="px-3 py-2 text-muted font-normal">progress</th>
                <th className="px-3 py-2 text-muted font-normal">load / cap</th>
                <th className="px-3 py-2 text-muted font-normal">fuel left</th>
                <th className="px-3 py-2 text-muted font-normal">CO2</th>
                <th className="px-3 py-2 text-muted font-normal">neighbors</th>
                <th className="px-3 py-2 text-muted font-normal">action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-rule bg-panel">
              {vehicles.map((v, i) => {
                const isSelected = selectedVehicleId === v.id;
                const isBroken = v.status === "BROKEN_DOWN";
                return (
                  <tr
                    key={v.id}
                    onClick={() => setSelectedVehicleId(isSelected ? null : v.id)}
                    className={`cursor-pointer transition-colors ${
                      isSelected
                        ? "bg-[#e9e9e0]"
                        : isBroken
                        ? "bg-[#faecea]"
                        : i % 2 === 1
                        ? "bg-panel2"
                        : ""
                    } hover:bg-[#e2e2d8]`}
                  >
                    <td className="px-3 py-2 font-bold text-ink">{v.id}</td>
                    <td className="px-3 py-2">
                      <span
                        className={`px-1.5 py-0.5 border text-[10px] ${
                          isBroken
                            ? "border-red text-red font-bold"
                            : v.status === "EN_ROUTE"
                            ? "border-green text-green"
                            : "border-rule text-muted"
                        }`}
                      >
                        {v.status}
                      </span>
                    </td>
                    <td className="px-3 py-2 text-muted">
                      ({v.x.toFixed(1)}, {v.y.toFixed(1)})
                    </td>
                    <td className="px-3 py-2">{v.speed_kmh} km/h</td>
                    <td className="px-3 py-2">
                      <div className="flex items-center gap-2">
                        <div className="w-12 h-1.5 bg-rule rounded-full overflow-hidden">
                          <div
                            className="h-full bg-ink"
                            style={{ width: `${v.route_progress}%` }}
                          />
                        </div>
                        <span>{v.route_progress}%</span>
                      </div>
                    </td>
                    <td className="px-3 py-2">
                      {v.current_load} / {v.max_weight} kg
                    </td>
                    <td className="px-3 py-2">{v.fuel_level} L</td>
                    <td className="px-3 py-2">{v.co2_kg} kg</td>
                    <td className="px-3 py-2 text-muted">
                      {v.mesh_neighbors.length > 0 ? v.mesh_neighbors.join(", ") : "—"}
                    </td>
                    <td className="px-3 py-2 text-ink font-semibold">{v.last_action}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {/* Selected Vehicle Inspector Drawer */}
        {selectedVehicle && (
          <div className="mt-4 border border-ink bg-panel p-4 text-xs mono">
            <div className="flex items-center justify-between border-b border-rule pb-2">
              <span className="serif text-base text-ink font-semibold">
                Vehicle Inspector — {selectedVehicle.id}
              </span>
              <button
                onClick={() => setSelectedVehicleId(null)}
                className="text-muted hover:text-ink"
              >
                ✕ close
              </button>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 pt-3">
              <div>
                <span className="text-muted block">edge position</span>
                <span className="text-ink font-semibold">{selectedVehicle.edge}</span>
              </div>
              <div>
                <span className="text-muted block">assigned tour</span>
                <span className="text-ink">
                  {selectedVehicle.current_route.join(" → ") || "None"}
                </span>
              </div>
              <div>
                <span className="text-muted block">assigned orders</span>
                <span className="text-ink">
                  {selectedVehicle.assigned_orders.join(", ") || "None"}
                </span>
              </div>
              <div>
                <span className="text-muted block">estimated completion</span>
                <span className="text-ink">ETA +{selectedVehicle.eta_mins} mins</span>
              </div>
            </div>
          </div>
        )}
      </Section>

      {/* 6. Live Order Table & Details */}
      <Section index="4" title="Order Monitoring">
        <div className="border border-ink overflow-x-auto max-h-80 overflow-y-auto">
          <table className="w-full text-xs mono">
            <thead className="sticky top-0 bg-panel2 border-b border-ink">
              <tr className="text-left">
                <th className="px-3 py-2 text-muted font-normal">order id</th>
                <th className="px-3 py-2 text-muted font-normal">customer</th>
                <th className="px-3 py-2 text-muted font-normal">assigned truck</th>
                <th className="px-3 py-2 text-muted font-normal">status</th>
                <th className="px-3 py-2 text-muted font-normal">demand</th>
                <th className="px-3 py-2 text-muted font-normal">priority</th>
                <th className="px-3 py-2 text-muted font-normal">deadline</th>
                <th className="px-3 py-2 text-muted font-normal">eta</th>
                <th className="px-3 py-2 text-muted font-normal">delay</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-rule bg-panel">
              {orders.map((o, i) => {
                const isSelected = selectedOrderId === o.id;
                const isDelivered = o.status === "DELIVERED";
                const isLate = o.status === "LATE";
                return (
                  <tr
                    key={o.id}
                    onClick={() => setSelectedOrderId(isSelected ? null : o.id)}
                    className={`cursor-pointer transition-colors ${
                      isSelected ? "bg-[#e9e9e0]" : i % 2 === 1 ? "bg-panel2" : ""
                    } hover:bg-[#e2e2d8]`}
                  >
                    <td className="px-3 py-2 font-bold text-ink">{o.id}</td>
                    <td className="px-3 py-2">Customer #{o.customer_id}</td>
                    <td className="px-3 py-2 text-muted">{o.assigned_vehicle || "UNASSIGNED"}</td>
                    <td className="px-3 py-2">
                      <span
                        className={`px-1.5 py-0.5 border text-[10px] ${
                          isDelivered
                            ? "border-green text-green"
                            : isLate
                            ? "border-red text-red font-bold"
                            : "border-rule text-muted"
                        }`}
                      >
                        {o.status}
                      </span>
                    </td>
                    <td className="px-3 py-2">{o.demand} kg</td>
                    <td className="px-3 py-2">{o.priority}</td>
                    <td className="px-3 py-2">{o.deadline}m</td>
                    <td className="px-3 py-2">{o.eta}m</td>
                    <td className="px-3 py-2">
                      {o.delay > 0 ? (
                        <span className="text-red font-semibold">+{o.delay}m</span>
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
          <div className="mt-3 border border-ink bg-panel p-3 text-xs mono">
            <div className="flex justify-between border-b border-rule pb-1.5">
              <span className="font-semibold text-ink">
                Order Details: {selectedOrder.id}
              </span>
              <button onClick={() => setSelectedOrderId(null)} className="text-muted">
                ✕
              </button>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-2">
              <div>Coordinates: ({selectedOrder.x.toFixed(1)}, {selectedOrder.y.toFixed(1)})</div>
              <div>Time Window: [{selectedOrder.ready_time}m, {selectedOrder.deadline}m]</div>
              <div>Remaining Distance: {selectedOrder.distance_remaining} km</div>
              <div>Delivery Status: {selectedOrder.status}</div>
            </div>
          </div>
        )}
      </Section>

      {/* 7. PPO Reinforcement Learning & Predictive Intelligence */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* PPO Operational Telemetry */}
        <div className="border border-ink bg-panel p-4 space-y-3">
          <div className="flex items-center justify-between border-b border-rule pb-2">
            <span className="mono text-xs text-muted">reinforcement learning</span>
            <span className="mono text-[11px] text-green border border-green px-2 py-0.5">
              {ppo.policy_status}
            </span>
          </div>
          <div className="grid grid-cols-3 gap-2 mono text-xs">
            <div className="border border-rule bg-paper p-2">
              <span className="text-muted text-[10px] block">current action</span>
              <span className="font-bold text-ink">{ppo.current_action}</span>
            </div>
            <div className="border border-rule bg-paper p-2">
              <span className="text-muted text-[10px] block">step reward</span>
              <span className="font-bold text-green">{ppo.current_reward > 0 ? `+${ppo.current_reward}` : ppo.current_reward}</span>
            </div>
            <div className="border border-rule bg-paper p-2">
              <span className="text-muted text-[10px] block">cumulative reward</span>
              <span className="font-bold text-ink">{ppo.episode_reward}</span>
            </div>
          </div>

          <div className="mono text-xs text-muted pt-1">recent PPO decisions:</div>
          <div className="border border-rule overflow-x-auto max-h-36 overflow-y-auto">
            <table className="w-full text-[11px] mono">
              <thead>
                <tr className="text-left bg-panel2 border-b border-rule">
                  <th className="px-2 py-1 text-muted">time</th>
                  <th className="px-2 py-1 text-muted">action</th>
                  <th className="px-2 py-1 text-muted">reward</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-rule bg-panel">
                {ppo.history.length === 0 ? (
                  <tr>
                    <td colSpan={3} className="px-2 py-3 text-center text-muted">
                      Waiting for decision ticks...
                    </td>
                  </tr>
                ) : (
                  ppo.history.slice(-8).map((h, idx) => (
                    <tr key={idx}>
                      <td className="px-2 py-1 text-muted">T+{h.time}m</td>
                      <td className="px-2 py-1 text-ink">{h.action}</td>
                      <td className="px-2 py-1 text-green font-semibold">
                        {h.reward > 0 ? `+${h.reward}` : h.reward}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Predictive Spatial Demand & Fleet Positioning */}
        <div className="border border-ink bg-panel p-4 space-y-3">
          <div className="flex items-center justify-between border-b border-rule pb-2">
            <span className="mono text-xs text-muted">spatial demand forecasting</span>
            <span className="mono text-[11px] text-muted">DemandPredictor</span>
          </div>

          <table className="w-full text-xs mono">
            <thead>
              <tr className="text-left bg-panel2 border-b border-rule">
                <th className="px-2 py-1 text-muted">zone</th>
                <th className="px-2 py-1 text-muted">predicted</th>
                <th className="px-2 py-1 text-muted">actual</th>
                <th className="px-2 py-1 text-muted">diff</th>
                <th className="px-2 py-1 text-muted">trend</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-rule bg-panel">
              {predictions.zones.map((z, idx) => (
                <tr key={idx}>
                  <td className="px-2 py-1 font-semibold text-ink">{z.zone}</td>
                  <td className="px-2 py-1">{z.predicted_demand} /hr</td>
                  <td className="px-2 py-1 text-muted">{z.actual_demand} /hr</td>
                  <td className="px-2 py-1">{z.diff}</td>
                  <td className="px-2 py-1 text-ink">{z.trend}</td>
                </tr>
              ))}
            </tbody>
          </table>

          {positioning.length > 0 && (
            <div className="mt-2 p-2 border border-rule bg-paper text-xs mono">
              <span className="text-green font-semibold">
                Proactive Repositioning Active:
              </span>
              <div className="mt-1 text-muted text-[11px]">
                {positioning[0].vehicle_id} relocating ({positioning[0].current_zone} → {positioning[0].target_zone}) to meet forecasted demand surge.
              </div>
            </div>
          )}
        </div>
      </div>

      {/* 8. Live Chronological Event Log & Timeline */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Live Event Log Feed */}
        <Section index="5" title="Live Event Feed">
          <div className="border border-ink bg-panel max-h-72 overflow-y-auto divide-y divide-rule mono text-xs">
            {events.length === 0 ? (
              <div className="p-4 text-center text-muted">No events recorded.</div>
            ) : (
              events.map((ev) => (
                <div key={ev.id} className="p-2.5 flex items-start gap-3 hover:bg-panel2">
                  <span className="text-muted shrink-0 text-[11px] pt-0.5">{ev.time_str}</span>
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <span
                        className={`text-[10px] px-1 border font-semibold ${
                          ev.severity === "DANGER"
                            ? "border-red text-red"
                            : ev.severity === "WARNING"
                            ? "border-amber text-amber"
                            : ev.severity === "SUCCESS"
                            ? "border-green text-green"
                            : "border-rule text-muted"
                        }`}
                      >
                        {ev.type}
                      </span>
                      <span className="text-ink font-semibold">{ev.target}</span>
                    </div>
                    <p className="text-muted text-[11px] mt-0.5 leading-snug">
                      {ev.description}
                    </p>
                  </div>
                </div>
              ))
            )}
          </div>
        </Section>

        {/* Milestone Timeline */}
        <Section index="6" title="Simulation Milestone Timeline">
          <div className="border border-ink bg-panel p-4 max-h-72 overflow-y-auto">
            <ol className="relative border-l border-rule ml-3 space-y-4 mono text-xs">
              {timeline.map((t, idx) => (
                <li key={idx} className="ml-4">
                  <div className="absolute -left-1.5 mt-1 w-3 h-3 rounded-full border border-ink bg-paper" />
                  <span className="text-[10px] text-muted block">{t.time_str}</span>
                  <span className="text-ink font-semibold text-xs block">{t.title}</span>
                  <span className="text-muted text-[11px] leading-snug">{t.description}</span>
                </li>
              ))}
            </ol>
          </div>
        </Section>
      </div>
    </div>
  );
}
