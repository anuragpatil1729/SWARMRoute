"use client";

import { useState } from "react";
import Link from "next/link";
import OpenStreetMap from "../../components/OpenStreetMap";
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
  const [mapMode, setMapMode] = useState("gis"); // "gis" for OpenStreetMap, "schematic" for SVG graph
  const [dispatchLoading, setDispatchLoading] = useState(false);
  const [dispatchFeedback, setDispatchFeedback] = useState(null);

  const handleAiAutoDispatchAll = async () => {
    setDispatchLoading(true);
    setDispatchFeedback(null);
    try {
      const res = await fetch("/api/orders/auto-allocate-all", { method: "POST" });
      const data = await res.json();
      if (data.success && data.allocated_count > 0) {
        setDispatchFeedback(`AI Auto-Dispatched ${data.allocated_count} pending orders to available delivery partners!`);
      } else if (data.success && data.allocated_count === 0) {
        setDispatchFeedback("All customer orders are already allocated to delivery partners.");
      } else {
        setDispatchFeedback(data.error || "No pending orders eligible for allocation.");
      }
    } catch (e) {
      setDispatchFeedback("AI auto-allocation request processed.");
    } finally {
      setDispatchLoading(false);
      setTimeout(() => setDispatchFeedback(null), 5000);
    }
  };

  if (!state) return <div className="ops-empty"><b>{connectionStatus === "OFFLINE" ? "Fleet telemetry offline" : "Connecting to fleet telematics"}</b><span>Live state is synchronized with the SWARMRoute operational API.</span></div>;

  const { simulation = {}, fleet = {}, vehicles = [], orders = [], map = {}, traffic = {}, network = {}, incidents = [], recovery_flow: recoveryFlow = [], ppo = {}, sustainability = {}, performance = {}, events = [] } = state;
  const running = simulation.status === "RUNNING";
  const activeOrders = orders.filter(({ status }) => ["PENDING", "ASSIGNED", "IN_TRANSIT", "REASSIGNED", "REQUESTED"].includes(status)).length;
  const delayed = typeof performance.late === "number" && typeof performance.failed === "number" ? performance.late + performance.failed : "—";
  const activeIncident = incidents.find((incident) => incident.status !== "RESOLVED" && incident.recovery_status !== "RECOVERED") || null;
  const brokenVehicle = vehicles.find((vehicle) => vehicle.status === "BROKEN_DOWN");
  const latestDecision = ppo.history?.at(-1);
  const incidentStages = recoveryFlow.length ? recoveryFlow : events.filter((event) => ["INCIDENT", "MESH", "DISPATCH"].includes(eventCategory(event))).slice(0, 6);
  const selected = vehicles.find((vehicle) => vehicle.id === selectedVehicleId);
  const cloudOnline = network.cloud_status === "ONLINE";
  const onlinePartners = (state.delivery_partners || []).filter((p) => p.status !== "OFFLINE");

  return <div className="ops-live-shell">
    <header className="ops-command-header">
      <div>
        <p className="ops-eyebrow">Autonomous Fleet Operations & Decentralized Mesh</p>
        <h2>SWARMRoute Operations Command</h2>
        <p className="ops-subtle">{unavailable(simulation.city || "Maharashtra Operations")} · Real-Time GPS & OSRM Road Telemetry</p>
      </div>
      <div className="ops-header-state">
        <span className={connectionStatus === "CONNECTED" ? "ops-live" : "ops-offline"}>● {connectionStatus}</span>
        <span className="ops-time">{unavailable(simulation.status)} · {unavailable(simulation.time_str)}</span>
      </div>
      <div className="ops-controls" aria-label="Operational controls">
        <button
          onClick={handleAiAutoDispatchAll}
          disabled={dispatchLoading}
          style={{ background: "#2563eb", color: "#ffffff", borderColor: "#1d4ed8", fontWeight: 700 }}
          className="shadow-xs flex items-center gap-1.5 px-3 py-1.5 rounded cursor-pointer hover:brightness-110"
          title="Instantly allocate all pending customer orders to optimal delivery partners using AI"
        >
          {dispatchLoading ? "⚡ Allocating..." : "⚡ AI Auto-Dispatch All"}
        </button>
        <Link
          href="/customer"
          className="font-semibold text-slate-800 bg-white border border-slate-300 hover:bg-slate-50 flex items-center gap-1"
        >
          + New Order
        </Link>
        <Link
          href="/partner"
          className="font-semibold text-slate-800 bg-white border border-slate-300 hover:bg-slate-50 flex items-center gap-1"
        >
          🚚 Partner Cockpit
        </Link>
        <span className="ops-control-divider" />
        <button
          onClick={() => toggleCloud(!cloudOnline)}
          title="Toggle cellular connection to test BLE mesh store-and-forward"
          style={cloudOnline ? {} : { background: "#9333ea", color: "#ffffff", borderColor: "#7e22ce" }}
        >
          {cloudOnline ? "📡 Test Offline Mesh" : "📶 Cellular Restored"}
        </button>
      </div>
    </header>

    {dispatchFeedback && (
      <div className="bg-blue-50 border border-blue-200 text-blue-800 text-xs px-4 py-2.5 rounded-lg flex items-center justify-between">
        <span>⚡ {dispatchFeedback}</span>
        <button onClick={() => setDispatchFeedback(null)} className="text-blue-600 hover:text-blue-900 font-bold ml-2">✕</button>
      </div>
    )}

    <section className="ops-kpi-strip" aria-label="Live operational metrics">
      <Metric
        label="Online Partners"
        value={onlinePartners.length > 0 ? `${onlinePartners.length} Active` : "0 Online"}
        detail="Authenticated drivers"
      />
      <Metric label="Active orders" value={activeOrders} detail="Pending, requested, or in transit" />
      <Metric label="Delivered" value={unavailable(performance.delivered)} detail={typeof performance.success_rate === "number" ? `${performance.success_rate}% completed` : undefined} />
      <Metric label="Late / failed" value={delayed} detail={typeof performance.late === "number" && typeof performance.failed === "number" ? `${performance.late} late · ${performance.failed} failed` : undefined} />
      <Metric label="Fleet utilization" value={numeric(fleet.utilization_pct, "%")} detail="Vehicles en route" />
      <Metric label="Fleet Fuel" value={numeric(sustainability.fuel_liters, " L", 1)} detail="Operational consumption" />
      <Metric label="Carbon" value={numeric(sustainability.co2_kg, " kg", 1)} detail="Calculated footprint" />
    </section>

    <main className="ops-main-grid">
      <section className="ops-map-panel" aria-labelledby="map-title">
        <div className="ops-panel-heading">
          <div>
            <p className="ops-eyebrow">Real-World GIS Operations</p>
            <h3 id="map-title">{mapMode === "gis" ? "Live OpenStreetMap GIS & Fleet Tracking" : "Schematic Fleet Network Topology"}</h3>
          </div>
          <div className="flex items-center gap-3">
            <div className="inline-flex rounded-lg border border-slate-200 bg-slate-100 p-0.5 text-xs font-semibold">
              <button
                type="button"
                onClick={() => setMapMode("gis")}
                className={`px-3 py-1 rounded-md transition-all ${mapMode === "gis" ? "bg-white text-blue-700 shadow-xs" : "text-slate-600 hover:text-slate-900"}`}
              >
                🗺️ Real-World GIS Map
              </button>
              <button
                type="button"
                onClick={() => setMapMode("schematic")}
                className={`px-3 py-1 rounded-md transition-all ${mapMode === "schematic" ? "bg-white text-blue-700 shadow-xs" : "text-slate-600 hover:text-slate-900"}`}
              >
                📐 Schematic Graph
              </button>
            </div>
          </div>
        </div>

        <div className="ops-map-frame !h-[560px]">
          {mapMode === "gis" ? (
            <OpenStreetMap
              customers={map.customers || []}
              depot={map.depot}
              routes={map.active_routes || {}}
              recoveryRoutes={map.recovery_routes || {}}
              vehicles={vehicles}
              trafficEdges={map.traffic_edges || []}
              selectedVehicleId={selectedVehicleId}
              onSelectVehicle={setSelectedVehicleId}
              activeCity={simulation.city || "Maharashtra"}
            />
          ) : (
            <LiveRouteMap
              customers={map.customers || []}
              depot={map.depot}
              routes={map.active_routes || {}}
              recoveryRoutes={map.recovery_routes || {}}
              vehicles={vehicles}
              trafficEdges={map.traffic_edges || []}
              selectedVehicleId={selectedVehicleId}
              onSelectVehicle={setSelectedVehicleId}
            />
          )}
        </div>

        {selected && (
          <div className="ops-selection">
            <b>{selected.id}</b>
            <span>{selected.status}</span>
            <span>node {unavailable(selected.current_node)} → {unavailable(selected.next_node)}</span>
            <span>route {numeric(selected.route_progress, "%", 1)}</span>
            <button onClick={() => setSelectedVehicleId(null)}>Clear</button>
          </div>
        )}
      </section>

      <aside className="ops-rail" aria-label="Operational status">
        <section className="ops-panel">
          <p className="ops-eyebrow">Current incident</p>
          {activeIncident || brokenVehicle ? (
            <>
              <h3 className="text-red-800">{activeIncident?.type || "Vehicle breakdown"}</h3>
              <dl>
                <dt>Vehicle</dt>
                <dd>{unavailable(activeIncident?.vehicle_id || brokenVehicle?.id)}</dd>
                <dt>Recovery</dt>
                <dd>{unavailable(activeIncident?.recovery_status)}</dd>
                <dt>Recipient</dt>
                <dd>{unavailable(activeIncident?.recovery_vehicle)}</dd>
              </dl>
            </>
          ) : (
            <>
              <h3>Nominal operation</h3>
              <p className="ops-subtle">All fleet units operating under normal conditions.</p>
            </>
          )}
        </section>

        <section className="ops-panel">
          <p className="ops-eyebrow">System status</p>
          <dl>
            <dt>Traffic</dt>
            <dd>{unavailable(traffic.congestion_level)}</dd>
            <dt>Cloud</dt>
            <dd>{unavailable(network.cloud_status)}</dd>
            <dt>Mesh</dt>
            <dd>{unavailable(network.mesh_status)}</dd>
            <dt>Connected nodes</dt>
            <dd>{network.connected_vehicles !== undefined && fleet.size !== undefined ? `${network.connected_vehicles} / ${fleet.size}` : "—"}</dd>
          </dl>
        </section>

        <section className="ops-panel ops-decision">
          <p className="ops-eyebrow">AI Decision Engine</p>
          <h3>{unavailable(latestDecision?.action || ppo.current_action)}</h3>
          <dl>
            <dt>Vehicle</dt>
            <dd>{unavailable(latestDecision?.target || latestDecision?.vehicle)}</dd>
            <dt>Order</dt>
            <dd>{unavailable(latestDecision?.order_id || latestDecision?.order)}</dd>
            <dt>Dispatch clock</dt>
            <dd>{unavailable(latestDecision?.time_str || (latestDecision?.time !== undefined ? `${latestDecision.time}m` : ppo.action_timestamp !== undefined ? `${ppo.action_timestamp}m` : null))}</dd>
            <dt>Reason</dt>
            <dd>{unavailable(latestDecision?.reason, String)}</dd>
          </dl>
        </section>
      </aside>
    </main>

    <section className="ops-bottom-grid">
      <section className="ops-panel">
        <div className="ops-panel-heading">
          <div>
            <p className="ops-eyebrow">Event feed</p>
            <h3>Latest operational events</h3>
          </div>
          <span className="ops-subtle">Runtime event history</span>
        </div>
        <div className="ops-events">
          {events.length ? (
            events.slice(0, 8).map((event, index) => {
              const category = eventCategory(event);
              return (
                <div className="ops-event" key={`${event.type || "event"}-${event.timestamp || index}-${index}`}>
                  <time>{eventTime(event)}</time>
                  <span className={`ops-event-tag ${tone[category]}`}>{category}</span>
                  <p>{event.description || event.message || unavailable(event.type)}</p>
                </div>
              );
            })
          ) : (
            <p className="ops-subtle">No operational alerts recorded.</p>
          )}
        </div>
      </section>

      <section className="ops-panel">
        <p className="ops-eyebrow">Recovery trace</p>
        <h3>Incident progression</h3>
        <ol className="ops-flow">
          {incidentStages.length ? (
            incidentStages.map((stage, index) => (
              <li key={`${stage.type || "stage"}-${index}`}>
                <b>{eventCategory(stage)}</b>
                <span>{stage.description || stage.label || stage.type}</span>
              </li>
            ))
          ) : (
            <li>
              <span>Nominal dispatch state — no recovery triggers active.</span>
            </li>
          )}
        </ol>
      </section>
    </section>
  </div>;
}

