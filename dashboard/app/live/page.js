"use client";

import { useState } from "react";
import LiveRouteMap from "../../components/LiveRouteMap";
import { useDashboardState } from "../../lib/useDashboardState";
import { eventCategory, eventTime, numeric, unavailable } from "../../lib/presentation";

const tone = {
  INCIDENT: "border-red-200 bg-red-50 text-red-800",
  TRAFFIC: "border-amber-200 bg-amber-50 text-amber-800",
  MESH: "border-blue-200 bg-blue-50 text-blue-800",
  DISPATCH: "border-violet-200 bg-violet-50 text-violet-800",
  DECISION: "border-slate-300 bg-slate-100 text-slate-800",
  DELIVERY: "border-emerald-200 bg-emerald-50 text-emerald-800",
  SYSTEM: "border-slate-200 bg-slate-50 text-slate-700",
};

function Metric({ label, value, detail }) {
  return <div className="ops-metric"><span>{label}</span><strong>{value}</strong>{detail && <small>{detail}</small>}</div>;
}

export default function LivePage() {
  const { state, connectionStatus, start, pause, step, reset, breakVehicle, toggleCloud, injectTraffic, injectDemand } = useDashboardState();
  const [selectedVehicleId, setSelectedVehicleId] = useState(null);

  if (!state) return <div className="ops-empty"><b>{connectionStatus === "OFFLINE" ? "Simulation offline" : "Connecting to simulation"}</b><span>Live state is read from the SWARMRoute simulation API.</span></div>;

  const { simulation = {}, fleet = {}, vehicles = [], orders = [], map = {}, traffic = {}, network = {}, incidents = [], recovery_flow: recoveryFlow = [], ppo = {}, sustainability = {}, performance = {}, events = [] } = state;
  const running = simulation.status === "RUNNING";
  const activeOrders = orders.filter(({ status }) => ["PENDING", "ASSIGNED", "IN_TRANSIT", "REASSIGNED"].includes(status)).length;
  const delayed = typeof performance.late === "number" && typeof performance.failed === "number" ? performance.late + performance.failed : "—";
  const activeIncident = incidents.find((incident) => incident.status !== "RESOLVED" && incident.recovery_status !== "RECOVERED") || null;
  const brokenVehicle = vehicles.find((vehicle) => vehicle.status === "BROKEN_DOWN");
  const latestDecision = ppo.history?.at(-1);
  const incidentStages = recoveryFlow.length ? recoveryFlow : events.filter((event) => ["INCIDENT", "MESH", "DISPATCH"].includes(eventCategory(event))).slice(0, 6);
  const selected = vehicles.find((vehicle) => vehicle.id === selectedVehicleId);
  const cloudOnline = network.cloud_status === "ONLINE";

  return <div className="ops-live-shell">
    <header className="ops-command-header">
      <div><p className="ops-eyebrow">Fleet operations / live simulation</p><h2>SWARMRoute Command Center</h2><p className="ops-subtle">{unavailable(simulation.city || simulation.dataset)} · simulation-coordinate telemetry</p></div>
      <div className="ops-header-state"><span className={connectionStatus === "CONNECTED" ? "ops-live" : "ops-offline"}>● {connectionStatus}</span><span className="ops-time">{unavailable(simulation.status)} · {unavailable(simulation.time_str)}</span></div>
      <div className="ops-controls" aria-label="Simulation controls">
        <button onClick={running ? pause : start}>{running ? "Pause" : "Start"}</button><button onClick={step} disabled={running}>Step</button><button onClick={() => reset()}>Reset</button>
        <span className="ops-control-divider" /><button onClick={() => injectTraffic(null, null, "SEVERE")}>Traffic</button><button onClick={() => breakVehicle()}>Breakdown</button><button onClick={() => toggleCloud(!cloudOnline)}>{cloudOnline ? "Cut cloud" : "Restore cloud"}</button><button onClick={() => injectDemand()}>Demand</button>
      </div>
    </header>

    <section className="ops-kpi-strip" aria-label="Live operational metrics">
      <Metric label="Active vehicles" value={fleet.available !== undefined && fleet.size !== undefined ? `${fleet.available} / ${fleet.size}` : "—"} detail={fleet.broken ? `${fleet.broken} unavailable` : undefined} />
      <Metric label="Active orders" value={activeOrders} detail="Pending, assigned, or in transit" />
      <Metric label="Delivered" value={unavailable(performance.delivered)} detail={typeof performance.success_rate === "number" ? `${performance.success_rate}% completed` : undefined} />
      <Metric label="Late / failed" value={delayed} detail={typeof performance.late === "number" && typeof performance.failed === "number" ? `${performance.late} late · ${performance.failed} failed` : undefined} />
      <Metric label="Fleet utilization" value={numeric(fleet.utilization_pct, "%")} detail="Vehicles en route" />
      <Metric label="Fuel" value={numeric(sustainability.fuel_liters, " L", 1)} detail="Consumed by simulation" />
      <Metric label="CO₂" value={numeric(sustainability.co2_kg, " kg", 1)} detail="Simulation estimate" />
    </section>

    <main className="ops-main-grid">
      <section className="ops-map-panel" aria-labelledby="map-title">
        <div className="ops-panel-heading"><div><p className="ops-eyebrow">Simulation map</p><h3 id="map-title">Live routes and fleet position</h3></div><div className="ops-legend"><span><i className="route" />Route</span><span><i className="recovery" />Recovery</span><span><i className="traffic" />Congestion</span></div></div>
        <div className="ops-map-frame"><LiveRouteMap customers={map.customers || []} depot={map.depot} routes={map.active_routes || {}} recoveryRoutes={map.recovery_routes || {}} vehicles={vehicles} trafficEdges={map.traffic_edges || []} selectedVehicleId={selectedVehicleId} onSelectVehicle={setSelectedVehicleId} /></div>
        {selected && <div className="ops-selection"><b>{selected.id}</b><span>{selected.status}</span><span>node {unavailable(selected.current_node)} → {unavailable(selected.next_node)}</span><span>route {numeric(selected.route_progress, "%", 1)}</span><button onClick={() => setSelectedVehicleId(null)}>Clear</button></div>}
      </section>

      <aside className="ops-rail" aria-label="Operational status">
        <section className="ops-panel"><p className="ops-eyebrow">Current incident</p>{activeIncident || brokenVehicle ? <><h3 className="text-red-800">{activeIncident?.type || "Vehicle breakdown"}</h3><dl><dt>Vehicle</dt><dd>{unavailable(activeIncident?.vehicle_id || brokenVehicle?.id)}</dd><dt>Recovery</dt><dd>{unavailable(activeIncident?.recovery_status)}</dd><dt>Recipient</dt><dd>{unavailable(activeIncident?.recovery_vehicle)}</dd></dl></> : <><h3>Nominal operation</h3><p className="ops-subtle">No unresolved incident reported by the simulation.</p></>}</section>
        <section className="ops-panel"><p className="ops-eyebrow">System status</p><dl><dt>Traffic</dt><dd>{unavailable(traffic.congestion_level)}</dd><dt>Cloud</dt><dd>{unavailable(network.cloud_status)}</dd><dt>Mesh</dt><dd>{unavailable(network.mesh_status)}</dd><dt>Connected nodes</dt><dd>{network.connected_vehicles !== undefined && fleet.size !== undefined ? `${network.connected_vehicles} / ${fleet.size}` : "—"}</dd></dl></section>
        <section className="ops-panel ops-decision"><p className="ops-eyebrow">Decision engine</p><h3>{unavailable(latestDecision?.action || ppo.current_action)}</h3><dl><dt>Vehicle</dt><dd>{unavailable(latestDecision?.target || latestDecision?.vehicle)}</dd><dt>Order</dt><dd>{unavailable(latestDecision?.order_id || latestDecision?.order)}</dd><dt>Simulation time</dt><dd>{unavailable(latestDecision?.time_str || (latestDecision?.time !== undefined ? `${latestDecision.time}m` : ppo.action_timestamp !== undefined ? `${ppo.action_timestamp}m` : null))}</dd><dt>Reason</dt><dd>{unavailable(latestDecision?.reason, String)}</dd></dl></section>
      </aside>
    </main>

    <section className="ops-bottom-grid">
      <section className="ops-panel"><div className="ops-panel-heading"><div><p className="ops-eyebrow">Event feed</p><h3>Latest operational events</h3></div><span className="ops-subtle">Runtime event history</span></div><div className="ops-events">{events.length ? events.slice(0, 8).map((event, index) => { const category = eventCategory(event); return <div className="ops-event" key={`${event.type || "event"}-${event.timestamp || index}-${index}`}><time>{eventTime(event)}</time><span className={`ops-event-tag ${tone[category]}`}>{category}</span><p>{event.description || event.message || unavailable(event.type)}</p></div>; }) : <p className="ops-subtle">No events have been emitted by the simulation.</p>}</div></section>
      <section className="ops-panel"><p className="ops-eyebrow">Recovery trace</p><h3>Incident progression</h3><ol className="ops-flow">{incidentStages.length ? incidentStages.map((stage, index) => <li key={`${stage.type || "stage"}-${index}`}><b>{eventCategory(stage)}</b><span>{stage.description || stage.label || stage.type}</span></li>) : <li><span>No runtime recovery stages are available.</span></li>}</ol></section>
    </section>
  </div>;
}
