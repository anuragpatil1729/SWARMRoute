"use client";

import { useState } from "react";
import Section from "../../components/Section";
import Stat from "../../components/Stat";
import { useDashboardState } from "../../lib/useDashboardState";

export default function FleetPage() {
  const { state, connectionStatus } = useDashboardState();
  const [searchQuery, setSearchQuery] = useState("");
  const [filterStatus, setFilterStatus] = useState("ALL");

  if (connectionStatus === "OFFLINE" && !state) {
    return (
      <div className="py-16 text-center">
        <div className="border border-red-200 bg-white rounded-2xl shadow-sm p-8 max-w-lg mx-auto">
          <div className="font-mono text-xs text-red-600 font-bold uppercase tracking-wider">
            Connection Offline
          </div>
          <h2 className="text-xl font-bold text-slate-900 mt-2">FLEET TELEMETRY OFFLINE</h2>
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
          <div className="font-mono text-xs text-slate-400">Loading Fleet</div>
          <h2 className="text-xl font-bold text-slate-800 mt-1">CONNECTING TO VEHICLE TELEMETRY</h2>
          <p className="text-xs text-slate-500 mt-2">Streaming real-time commercial vehicle state...</p>
        </div>
      </div>
    );
  }

  const { fleet, vehicles = [], sustainability, performance } = state;

  const filteredVehicles = vehicles.filter((v) => {
    const matchesSearch =
      v.id.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (v.partner_name && v.partner_name.toLowerCase().includes(searchQuery.toLowerCase())) ||
      (v.registration && v.registration.toLowerCase().includes(searchQuery.toLowerCase()));
    const matchesStatus =
      filterStatus === "ALL" || v.status === filterStatus;
    return matchesSearch && matchesStatus;
  });

  return (
    <div className="space-y-6 w-full">
      {/* Header Banner */}
      <div className="border border-slate-200 bg-white rounded-xl shadow-sm p-5">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <div className="flex items-center gap-3">
              <h2 className="text-xl font-bold text-slate-900">
                Commercial Fleet Telemetry
              </h2>
              <span className="text-[11px] font-mono px-2.5 py-0.5 rounded bg-blue-50 text-blue-700 border border-blue-200 font-semibold">
                {vehicles.length} Deployed Units
              </span>
            </div>
            <p className="text-xs text-slate-500 mt-1">
              Real-time payload, remaining capacity, battery/fuel levels, GIS coordinates, and active stop sequences.
            </p>
          </div>

          {/* KPI Summary Cards */}
          <div className="flex items-center gap-2 flex-wrap">
            <div className="px-3 py-1.5 rounded-lg bg-emerald-50 border border-emerald-200 text-xs font-semibold text-emerald-800">
              Operational: {fleet.available} / {fleet.size}
            </div>
            <div className="px-3 py-1.5 rounded-lg bg-amber-50 border border-amber-200 text-xs font-semibold text-amber-800">
              Avg Utilization: {fleet.utilization_pct}%
            </div>
            {fleet.broken > 0 && (
              <div className="px-3 py-1.5 rounded-lg bg-red-50 border border-red-200 text-xs font-semibold text-red-700 animate-pulse">
                Broken Down: {fleet.broken}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* KPI Stats Row */}
      <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-6 gap-3">
        <Stat label="Total Vehicles" value={fleet.size} help="Active fleet units" />
        <Stat label="Operational" value={fleet.available} help={`${fleet.broken} broken down`} />
        <Stat label="Total Distance" value={`${sustainability.total_distance_km} km`} help="Cumulative distance" />
        <Stat label="Total Fuel / Energy" value={`${sustainability.fuel_liters} L`} help="Fleet consumption" />
        <Stat label="Total CO₂" value={`${sustainability.co2_kg} kg`} help="Emissions footprint" />
        <Stat label="Empty Running" value={`${sustainability.empty_km} km`} help="Deadhead transit" />
      </div>

      {/* Filter & Search Bar */}
      <div className="border border-slate-200 bg-white rounded-xl shadow-sm p-4 flex flex-col sm:flex-row items-center justify-between gap-3">
        <div className="flex items-center gap-2 w-full sm:w-auto">
          <span className="text-xs font-semibold text-slate-500 uppercase font-mono">Filter:</span>
          {["ALL", "EN_ROUTE", "IDLE", "BROKEN_DOWN", "REPOSITIONING"].map((status) => (
            <button
              key={status}
              onClick={() => setFilterStatus(status)}
              className={`px-3 py-1 rounded-lg text-xs font-medium transition ${
                filterStatus === status
                  ? "bg-blue-600 text-white shadow-xs"
                  : "bg-slate-100 text-slate-600 hover:bg-slate-200"
              }`}
            >
              {status.replace("_", " ")}
            </button>
          ))}
        </div>

        <input
          type="text"
          placeholder="Search partner, vehicle ID, registration..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="w-full sm:w-72 px-3 py-1.5 rounded-lg border border-slate-200 text-xs placeholder-slate-400 focus:outline-none focus:border-blue-500 font-mono"
        />
      </div>

      {/* Detailed Vehicles Table */}
      <div className="border border-slate-200 bg-white rounded-xl shadow-sm overflow-hidden">
        <div className="px-5 py-4 border-b border-slate-100 bg-slate-50/50 flex items-center justify-between">
          <h3 className="text-sm font-bold text-slate-900 uppercase font-mono">
            Vehicle Telematics Registry ({filteredVehicles.length})
          </h3>
          <span className="text-xs text-slate-400 font-mono">Live Simulation Synchronized</span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-50 border-b border-slate-200 text-slate-600 font-mono uppercase text-[11px]">
              <tr>
                <th className="py-3 px-4">Vehicle / Driver</th>
                <th className="py-3 px-3">Status</th>
                <th className="py-3 px-3">Speed</th>
                <th className="py-3 px-3">Payload / Capacity</th>
                <th className="py-3 px-3">Fuel / Energy</th>
                <th className="py-3 px-3">Route Progress</th>
                <th className="py-3 px-3">Assigned Orders</th>
                <th className="py-3 px-3">Connectivity</th>
                <th className="py-3 px-4">Mesh Peers</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 font-mono text-[12px]">
              {filteredVehicles.map((v) => {
                const isBroken = v.status === "BROKEN_DOWN";
                const isEnRoute = v.status === "EN_ROUTE";
                return (
                  <tr
                    key={v.id}
                    className={`hover:bg-slate-50/80 transition-colors ${
                      isBroken ? "bg-red-50/40" : ""
                    }`}
                  >
                    <td className="py-3 px-4 font-sans">
                      <div className="flex items-center gap-2.5">
                        <span className="text-lg">{v.avatar || "🚚"}</span>
                        <div>
                          <div className="font-bold text-slate-900">{v.partner_name || v.id}</div>
                          <div className="text-[11px] text-slate-500 font-mono">
                            {v.id} · {v.vehicle_model} ({v.registration})
                          </div>
                        </div>
                      </div>
                    </td>
                    <td className="py-3 px-3">
                      <span
                        className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-semibold ${
                          isBroken
                            ? "bg-red-100 text-red-800 border border-red-200 animate-pulse"
                            : isEnRoute
                            ? "bg-blue-50 text-blue-700 border border-blue-200"
                            : "bg-slate-100 text-slate-700 border border-slate-200"
                        }`}
                      >
                        {v.status}
                      </span>
                    </td>
                    <td className="py-3 px-3 text-slate-700">
                      {Math.round(v.speed_kmh)} km/h
                    </td>
                    <td className="py-3 px-3">
                      <div className="text-slate-800 font-semibold">
                        {v.current_load} / {v.max_weight} kg
                      </div>
                      <div className="text-[10px] text-slate-400">
                        Rem: {v.remaining_capacity} kg
                      </div>
                    </td>
                    <td className="py-3 px-3">
                      <div className="flex items-center gap-2">
                        <div className="w-16 bg-slate-200 rounded-full h-1.5 overflow-hidden">
                          <div
                            className={`h-full rounded-full ${
                              v.fuel_level < 25 ? "bg-red-500" : "bg-emerald-500"
                            }`}
                            style={{ width: `${Math.min(100, Math.max(0, v.fuel_level))}%` }}
                          />
                        </div>
                        <span className="text-[11px] text-slate-700 font-semibold">
                          {Math.round(v.fuel_level)}%
                        </span>
                      </div>
                      <div className="text-[10px] text-slate-400">
                        Used: {v.fuel_consumed} L
                      </div>
                    </td>
                    <td className="py-3 px-3">
                      <div className="text-slate-800 font-semibold">
                        {v.route_progress}%
                      </div>
                      <div className="text-[10px] text-slate-400">
                        {v.current_route?.length > 1
                          ? `${v.current_route.length} stops (ETA ~${v.eta_mins}m)`
                          : "Idle at Hub"}
                      </div>
                    </td>
                    <td className="py-3 px-3 text-slate-700">
                      {v.assigned_orders?.length > 0 ? (
                        <div className="flex flex-wrap gap-1">
                          {v.assigned_orders.map((oid) => (
                            <span
                              key={oid}
                              className="px-1.5 py-0.5 rounded bg-slate-100 border border-slate-200 text-[10px] font-semibold text-slate-800"
                            >
                              {oid}
                            </span>
                          ))}
                        </div>
                      ) : (
                        <span className="text-slate-400">None</span>
                      )}
                    </td>
                    <td className="py-3 px-3">
                      <span
                        className={`text-[11px] font-semibold ${
                          v.connectivity === "CLOUD_MODE"
                            ? "text-blue-600"
                            : "text-amber-600"
                        }`}
                      >
                        ● {v.connectivity}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-slate-500 text-[11px]">
                      {v.mesh_neighbors?.length > 0 ? (
                        <span>{v.mesh_neighbors.join(", ")}</span>
                      ) : (
                        <span className="text-slate-400">Isolated</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
