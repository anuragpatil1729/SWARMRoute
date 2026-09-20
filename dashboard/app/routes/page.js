"use client";

import OpenStreetMap from "../../components/OpenStreetMap";
import { useDashboardState } from "../../lib/useDashboardState";
import { getRouteMap } from "../../lib/data";

export default function RoutesPage() {
  const { state, connectionStatus } = useDashboardState();
  const fallback = getRouteMap();

  const isLive = connectionStatus !== "OFFLINE" && !!state;
  const customers = isLive && state.map?.customers?.length > 0 ? state.map.customers : fallback.customers;
  const depot = isLive && state.map?.depot ? state.map.depot : fallback.depot;
  const routes = isLive && state.map?.active_routes ? state.map.active_routes : fallback.routes;
  const recoveryRoutes = isLive && state.map?.recovery_routes ? state.map.recovery_routes : {};
  const vehicles = isLive ? (state.vehicles || []) : [];
  const trafficEdges = isLive ? (state.map?.traffic_edges || []) : [];
  const activeCity = isLive ? (state.simulation?.city || "Maharashtra") : "Maharashtra";

  const totalOrders = isLive ? (state.orders?.length || 0) : (customers.length - 1);
  const deliveredCount = isLive ? (state.performance?.delivered || 0) : 0;
  const activeVehiclesCount = vehicles.length;
  const totalDistanceKm = isLive ? Math.round(state.sustainability?.total_distance_km || 0) : Math.round(fallback.totalDistance || 0);

  return (
    <div className="space-y-6">
      <div className="border border-slate-200 bg-white p-5 rounded-xl shadow-sm">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h2 className="text-xl font-bold text-slate-900">
              Interactive Route Map
            </h2>
            <p className="text-xs text-slate-500 mt-1">
              Real-world OpenStreetMap GIS mapping with multi-stop vehicle tours and depot network.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <span className="px-2.5 py-1 text-xs font-mono bg-blue-50 text-blue-700 border border-blue-200 rounded font-semibold">
              Region: {activeCity}
            </span>
            <span className={`px-2.5 py-1 text-xs font-mono rounded font-semibold ${
              isLive ? "bg-emerald-50 text-emerald-700 border border-emerald-200" : "bg-slate-100 text-slate-600 border border-slate-200"
            }`}>
              {isLive ? "● LIVE TELEMETRY" : "STATIC BENCHMARK"}
            </span>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm">
          <span className="text-xs text-slate-400 font-mono block uppercase">Status</span>
          <span className="text-xl font-bold text-slate-800">
            {isLive ? (state.simulation?.status || "NOMINAL") : "OPTIMAL"}
          </span>
        </div>
        <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm">
          <span className="text-xs text-slate-400 font-mono block uppercase">Active Partners</span>
          <span className="text-xl font-bold text-slate-800">
            {activeVehiclesCount} <span className="text-sm font-normal text-slate-400">deployed</span>
          </span>
        </div>
        <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm">
          <span className="text-xs text-slate-400 font-mono block uppercase">Customer Orders</span>
          <span className="text-xl font-bold text-slate-800">
            {totalOrders} <span className="text-sm font-normal text-slate-400">({deliveredCount} done)</span>
          </span>
        </div>
        <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm">
          <span className="text-xs text-slate-400 font-mono block uppercase">Total Distance</span>
          <span className="text-xl font-bold text-slate-800">
            {totalDistanceKm} <span className="text-sm font-normal text-slate-400">km</span>
          </span>
        </div>
      </div>

      <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm space-y-3">
        <div className="flex items-center justify-between">
          <span className="text-sm font-semibold text-slate-800">
            OpenStreetMap Fleet Dispatch Tour
          </span>
          <span className="text-xs font-mono text-slate-400">
            OSM Cartographic Projection
          </span>
        </div>
        <OpenStreetMap
          customers={customers}
          depot={depot}
          routes={routes}
          recoveryRoutes={recoveryRoutes}
          vehicles={vehicles}
          trafficEdges={trafficEdges}
          activeCity={activeCity}
        />
      </div>
    </div>
  );
}
