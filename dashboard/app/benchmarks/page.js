import Section from "../../components/Section";
import MethodBarChart from "../../components/MethodBarChart";
import { getMethodComparison } from "../../lib/data";

export default function BenchmarksPage() {
  const methods = getMethodComparison();

  return (
    <div>
      <h1 className="text-2xl font-semibold text-white mb-1">Method comparison</h1>
      <p className="text-sm text-muted mb-8 max-w-2xl">
        Six routing strategies evaluated on the same single scenario (seed 101,
        Solomon C101). Nearest Neighbor and Random Policy are naive baselines;
        the interesting comparison is OR-Tools&apos; static plan against the
        decentralized and learned approaches.
      </p>

      <Section title="Delivery success" description="Percentage of orders delivered by the end of the horizon.">
        <MethodBarChart data={methods} dataKey="success" unit="%" />
      </Section>

      <Section title="On-time delivery" description="Percentage delivered within the customer time window.">
        <MethodBarChart data={methods} dataKey="onTime" unit="%" />
      </Section>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
        <Section title="Distance traveled" description="Total fleet distance, km.">
          <MethodBarChart data={methods} dataKey="distance" height={220} />
        </Section>
        <Section title="Fuel consumption" description="Total fleet fuel, liters.">
          <MethodBarChart data={methods} dataKey="fuel" height={220} />
        </Section>
      </div>

      <Section title="Full metrics table">
        <div className="border border-border overflow-x-auto">
          <table className="w-full text-sm min-w-[720px]">
            <thead>
              <tr className="text-left text-muted border-b border-border">
                <th className="font-normal px-4 py-3">Method</th>
                <th className="font-normal px-4 py-3">Success</th>
                <th className="font-normal px-4 py-3">On-time</th>
                <th className="font-normal px-4 py-3">Distance</th>
                <th className="font-normal px-4 py-3">Fuel</th>
                <th className="font-normal px-4 py-3">CO₂</th>
                <th className="font-normal px-4 py-3">Empty km</th>
                <th className="font-normal px-4 py-3">Utilization</th>
                <th className="font-normal px-4 py-3">Failed</th>
                <th className="font-normal px-4 py-3">Runtime</th>
              </tr>
            </thead>
            <tbody className="mono">
              {methods.map((m) => (
                <tr key={m.method} className="border-b border-border last:border-0">
                  <td className="px-4 py-3 text-white whitespace-nowrap">{m.method}</td>
                  <td className="px-4 py-3">{m.success}%</td>
                  <td className="px-4 py-3">{m.onTime}%</td>
                  <td className="px-4 py-3">{m.distance} km</td>
                  <td className="px-4 py-3">{m.fuel} L</td>
                  <td className="px-4 py-3">{m.co2} kg</td>
                  <td className="px-4 py-3">{m.emptyKm} km</td>
                  <td className="px-4 py-3">{m.utilization}%</td>
                  <td className="px-4 py-3">{m.failed}</td>
                  <td className="px-4 py-3">{m.runtime}s</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>
    </div>
  );
}
