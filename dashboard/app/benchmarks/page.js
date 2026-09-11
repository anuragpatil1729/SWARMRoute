import Section from "../../components/Section";
import MethodBarChart from "../../components/MethodBarChart";
import { getMethodComparison } from "../../lib/data";

export default function BenchmarksPage() {
  const methods = getMethodComparison();

  return (
    <div className="space-y-6">
      <div className="border border-slate-200 bg-white p-5 rounded-xl shadow-sm">
        <h2 className="text-xl font-bold text-slate-900">
          Routing Method Comparison
        </h2>
        <p className="text-xs text-slate-500 mt-1">
          Autonomous dispatch and peer-to-peer resilience evaluated against static baseline heuristics.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm space-y-2">
          <h3 className="text-sm font-bold text-slate-800">Delivery Success Rate</h3>
          <p className="text-xs text-slate-500">Percentage of orders successfully delivered to destination.</p>
          <MethodBarChart data={methods} dataKey="success" unit="%" />
        </div>

        <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm space-y-2">
          <h3 className="text-sm font-bold text-slate-800">On-Time Delivery Rate</h3>
          <p className="text-xs text-slate-500">Percentage of deliveries completed strictly within customer time windows.</p>
          <MethodBarChart data={methods} dataKey="onTime" unit="%" />
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm space-y-2">
          <h3 className="text-sm font-bold text-slate-800">Distance Traveled (km)</h3>
          <p className="text-xs text-slate-500">Total fleet distance across operational horizon.</p>
          <MethodBarChart data={methods} dataKey="distance" height={220} />
        </div>

        <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm space-y-2">
          <h3 className="text-sm font-bold text-slate-800">Fuel Consumption (Liters)</h3>
          <p className="text-xs text-slate-500">Total fuel consumed by active fleet.</p>
          <MethodBarChart data={methods} dataKey="fuel" height={220} />
        </div>
      </div>

      <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm space-y-3">
        <h3 className="text-sm font-bold text-slate-800">Complete Evaluation Metrics</h3>
        <div className="overflow-x-auto border border-slate-200 rounded-lg">
          <table className="w-full text-xs font-mono min-w-[760px]">
            <thead>
              <tr className="text-left border-b border-slate-200 bg-slate-50 text-slate-500 font-semibold">
                {["Method", "Success", "On-Time", "Distance", "Fuel", "CO2", "Empty KM", "Utilization", "Failed", "Runtime"].map((h) => (
                  <th key={h} className="px-4 py-2.5">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 bg-white">
              {methods.map((m, i) => (
                <tr key={m.method} className={`hover:bg-slate-50/70 transition ${i % 2 ? "bg-slate-50/30" : ""}`}>
                  <td className="px-4 py-2.5 font-bold text-slate-900 whitespace-nowrap">{m.method}</td>
                  <td className="px-4 py-2.5 text-slate-800">{m.success}%</td>
                  <td className="px-4 py-2.5 text-slate-800">{m.onTime}%</td>
                  <td className="px-4 py-2.5 text-slate-800">{m.distance} km</td>
                  <td className="px-4 py-2.5 text-slate-800">{m.fuel} L</td>
                  <td className="px-4 py-2.5 text-slate-800">{m.co2} kg</td>
                  <td className="px-4 py-2.5 text-slate-800">{m.emptyKm} km</td>
                  <td className="px-4 py-2.5 text-slate-800">{m.utilization}%</td>
                  <td className="px-4 py-2.5 text-slate-800">{m.failed}</td>
                  <td className="px-4 py-2.5 text-slate-500">{m.runtime}s</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
