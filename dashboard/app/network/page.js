"use client";

import Section from "../../components/Section";
import Stat from "../../components/Stat";
import LiveMeshFigure from "../../components/LiveMeshFigure";
import { useDashboardState } from "../../lib/useDashboardState";

export default function NetworkPage() {
  const { state, connectionStatus, toggleCloud } = useDashboardState();

  if (connectionStatus === "OFFLINE" && !state) {
    return (
      <div className="py-16 text-center">
        <div className="border border-red-200 bg-white rounded-2xl shadow-sm p-8 max-w-lg mx-auto">
          <div className="font-mono text-xs text-red-600 font-bold uppercase tracking-wider">
            Connection Offline
          </div>
          <h2 className="text-xl font-bold text-slate-900 mt-2">NETWORK TELEMETRY OFFLINE</h2>
          <p className="text-xs text-slate-500 mt-2 leading-relaxed">
            Please make sure the SWARMRoute backend is running at <code className="font-mono bg-slate-100 px-1 py-0.5 rounded text-slate-700">http://127.0.0.1:8000</code>.
          </p>
        </div>
      </div>
    );
  }

  if (!state) {
    return (
      <div className="py-16 text-center">
        <div className="border border-slate-200 bg-white rounded-2xl shadow-sm p-8 max-w-md mx-auto">
          <div className="font-mono text-xs text-slate-400">Loading Network</div>
          <h2 className="text-xl font-bold text-slate-800 mt-1">CONNECTING TO MESH NETWORK</h2>
          <p className="text-xs text-slate-500 mt-2">Scanning peer-to-peer RF communication topology...</p>
        </div>
      </div>
    );
  }

  const { network, mesh, fleet, incidents = [], events = [] } = state;
  const isCloudOnline = network.cloud_status === "ONLINE";

  const networkEvents = events.filter(
    (e) =>
      e.type === "MESH_RECOVERY" ||
      e.type === "CLOUD_TOGGLE" ||
      e.type === "BREAKDOWN" ||
      (e.description && e.description.toLowerCase().includes("mesh")) ||
      (e.description && e.description.toLowerCase().includes("cloud"))
  );

  return (
    <div className="space-y-6 w-full">
      {/* Header Banner */}
      <div className="border border-slate-200 bg-white rounded-xl shadow-sm p-5">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <div className="flex items-center gap-3">
              <h2 className="text-xl font-bold text-slate-900">
                Decentralized Mesh & Cloud Telecommunications
              </h2>
              <span
                className={`text-[11px] font-mono px-2.5 py-0.5 rounded font-semibold ${
                  isCloudOnline
                    ? "bg-blue-50 text-blue-700 border border-blue-200"
                    : "bg-amber-50 text-amber-800 border border-amber-200 animate-pulse"
                }`}
              >
                ● Mode: {network.mode}
              </span>
            </div>
            <p className="text-xs text-slate-500 mt-1">
              Multi-hop dynamic ad-hoc radio mesh network linking commercial trucks autonomously during cloud connectivity dropouts.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => toggleCloud(!isCloudOnline)}
              className={`px-3 py-1.5 rounded-lg text-xs font-mono font-bold transition shadow-xs flex items-center gap-1.5 ${
                isCloudOnline
                  ? "bg-amber-500 hover:bg-amber-600 text-white"
                  : "bg-blue-600 hover:bg-blue-700 text-white"
              }`}
            >
              <span>{isCloudOnline ? "⚡ Cut Cloud (Force Mesh Mode)" : "☁️ Restore Cloud Uplink"}</span>
            </button>
          </div>
        </div>
      </div>

      {/* Network KPIs */}
      <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-6 gap-3">
        <Stat
          label="Cloud Status"
          value={network.cloud_status}
          help={isCloudOnline ? "Active 4G/5G Uplink" : "BLACKOUT (Mesh Fallback)"}
        />
        <Stat
          label="Mesh Status"
          value={network.mesh_status}
          help="Decentralized 802.11p RF"
        />
        <Stat
          label="Connected Nodes"
          value={`${network.connected_vehicles} / ${fleet.size}`}
          help={`${mesh.links.length} dynamic peer links`}
        />
        <Stat
          label="Radio Range"
          value={`${mesh.transmission_range_km} km`}
          help="Direct vehicle-to-vehicle"
        />
        <Stat
          label="Avg Latency"
          value={`${network.avg_latency_ms} ms`}
          help="Single-hop packet transit"
        />
        <Stat
          label="Messages Relayed"
          value={network.messages_sent}
          help="Peer contract-net audits"
        />
      </div>

      {/* Mesh Graph & Link Details */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Topology Visualization */}
        <div className="lg:col-span-2 border border-slate-200 bg-white rounded-xl shadow-sm p-5">
          <div className="flex items-center justify-between border-b border-slate-100 pb-3 mb-4">
            <div>
              <h3 className="text-sm font-bold text-slate-900 uppercase font-mono">
                Dynamic Mesh Topology Graph
              </h3>
              <p className="text-xs text-slate-400 font-mono mt-0.5">
                Real-time geometric proximity links based on 30 km RF radius
              </p>
            </div>
            <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-slate-100 text-slate-600 border border-slate-200">
              {network.connected_components} Connected Subgraphs
            </span>
          </div>

          <div className="h-64 bg-slate-950 rounded-xl p-3 border border-slate-800 relative overflow-hidden">
            <LiveMeshFigure mesh={mesh} activeRecovery={incidents[0]} />
          </div>

          <div className="flex items-center justify-between mt-3 text-xs text-slate-500 font-mono">
            <div className="flex items-center gap-3">
              <span className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-full bg-emerald-500" /> Active Peer
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-full bg-red-500" /> Broken Down Node
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-4 h-0.5 bg-cyan-400" /> RF Link
              </span>
            </div>
            <span>Auto-Updated Every Simulation Step</span>
          </div>
        </div>

        {/* Link Matrix */}
        <div className="border border-slate-200 bg-white rounded-xl shadow-sm p-5">
          <div className="border-b border-slate-100 pb-3 mb-4">
            <h3 className="text-sm font-bold text-slate-900 uppercase font-mono">
              Active Peer Links ({mesh.links.length})
            </h3>
            <p className="text-xs text-slate-400 font-mono mt-0.5">Direct point-to-point radios</p>
          </div>

          <div className="space-y-2 max-h-64 overflow-y-auto">
            {mesh.links.length > 0 ? (
              mesh.links.map((link, i) => (
                <div
                  key={i}
                  className="p-2.5 rounded-lg bg-slate-50 border border-slate-200 flex items-center justify-between text-xs font-mono"
                >
                  <div className="flex items-center gap-2">
                    <span className="font-bold text-slate-800">{link.source}</span>
                    <span className="text-slate-400">⟷</span>
                    <span className="font-bold text-slate-800">{link.target}</span>
                  </div>
                  <span className="text-slate-500 text-[11px]">{link.distance} km</span>
                </div>
              ))
            ) : (
              <div className="text-center py-8 text-xs text-slate-400 font-mono">
                No active links within transmission radius
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Connectivity Event Log */}
      <div className="border border-slate-200 bg-white rounded-xl shadow-sm p-5">
        <div className="border-b border-slate-100 pb-3 mb-4">
          <h3 className="text-sm font-bold text-slate-900 uppercase font-mono">
            Telecommunications Event Audit Log
          </h3>
          <p className="text-xs text-slate-400 font-mono mt-0.5">
            Decentralized contract-net auctions, packet dispatches, and uplink switches
          </p>
        </div>

        <div className="space-y-2 max-h-48 overflow-y-auto font-mono text-xs">
          {networkEvents.length > 0 ? (
            networkEvents.map((ev, i) => (
              <div
                key={i}
                className="p-2.5 rounded-lg bg-slate-50 border border-slate-200 flex items-start gap-3"
              >
                <span className="text-slate-400 text-[11px] whitespace-nowrap mt-0.5">
                  {ev.time_str || `${ev.timestamp}m`}
                </span>
                <span className="px-1.5 py-0.5 rounded bg-blue-100 text-blue-800 text-[10px] font-bold">
                  {ev.type}
                </span>
                <span className="text-slate-700 flex-1">{ev.description}</span>
              </div>
            ))
          ) : (
            <div className="text-center py-6 text-xs text-slate-400 font-mono">
              Nominal mesh communications. No network disruption logged yet.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
