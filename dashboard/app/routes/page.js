import Section from "../../components/Section";
import Stat from "../../components/Stat";
import OpenStreetMap from "../../components/OpenStreetMap";
import { getRouteMap } from "../../lib/data";

export default function RoutesPage() {
  const { dataset, status, totalDistance, customers, depot, routes } = getRouteMap();

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
            <span className="px-2.5 py-1 text-xs font-mono bg-blue-50 text-blue-700 border border-blue-200 rounded">
              Dataset: {dataset}
            </span>
            <span className="px-2.5 py-1 text-xs font-mono bg-emerald-50 text-emerald-700 border border-emerald-200 rounded">
              {status}
            </span>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm">
          <span className="text-xs text-slate-400 font-mono block uppercase">Status</span>
          <span className="text-xl font-bold text-slate-800">{status}</span>
        </div>
        <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm">
          <span className="text-xs text-slate-400 font-mono block uppercase">Active Vehicles</span>
          <span className="text-xl font-bold text-slate-800">{routes.length} <span className="text-sm font-normal text-slate-400">/ 25</span></span>
        </div>
        <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm">
          <span className="text-xs text-slate-400 font-mono block uppercase">Deliveries</span>
          <span className="text-xl font-bold text-slate-800">{customers.length - 1}</span>
        </div>
        <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm">
          <span className="text-xs text-slate-400 font-mono block uppercase">Total Distance</span>
          <span className="text-xl font-bold text-slate-800">{totalDistance ? Math.round(totalDistance) : "—"} <span className="text-sm font-normal text-slate-400">km</span></span>
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
        <OpenStreetMap customers={customers} depot={depot} routes={routes} />
      </div>
    </div>
  );
}
