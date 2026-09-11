import Section from "../../components/Section";
import MethodBarChart from "../../components/MethodBarChart";
import { getMethodComparison } from "../../lib/data";

export default function BenchmarksPage() {
  const methods = getMethodComparison();

  return (
    <div>
      <Section index="1" title="Method comparison">
        <p className="text-sm text-muted max-w-2xl">
          Six routing strategies evaluated on the same single scenario (seed
          101, Solomon C101). Nearest Neighbor and Random Policy are naive
          baselines; the interesting comparison is OR-Tools&apos; static plan
          against the decentralized and learned approaches.
        </p>
      </Section>

      <Section index="2" title="Delivery success" description="Percentage of orders delivered by the end of the horizon.">
        <MethodBarChart data={methods} dataKey="success" unit="%" />
      </Section>

      <Section index="3" title="On-time delivery" description="Percentage delivered within the customer time window.">
        <MethodBarChart data={methods} dataKey="onTime" unit="%" />
      </Section>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
        <Section index="4" title="Distance traveled" description="Total fleet distance, km.">
          <MethodBarChart data={methods} dataKey="distance" height={220} />
        </Section>
        <Section index="5" title="Fuel consumption" description="Total fleet fuel, liters.">
          <MethodBarChart data={methods} dataKey="fuel" height={220} />
        </Section>
      </div>

      <Section index="6" title="Full metrics table">
        <div className="overflow-x-auto border border-ink">
          <table className="w-full text-sm min-w-[760px]">
            <thead>
              <tr className="text-left border-b border-ink">
                {["method", "success", "on-time", "distance", "fuel", "co2", "empty km", "utilization", "failed", "runtime"].map((h) => (
                  <th key={h} className="font-normal px-4 py-2.5 mono text-xs text-muted">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="mono">
              {methods.map((m, i) => (
                <tr key={m.method} className={i % 2 ? "bg-panel2" : ""}>
                  <td className="px-4 py-2.5 text-ink whitespace-nowrap">{m.method}</td>
                  <td className="px-4 py-2.5">{m.success}%</td>
                  <td className="px-4 py-2.5">{m.onTime}%</td>
                  <td className="px-4 py-2.5">{m.distance} km</td>
                  <td className="px-4 py-2.5">{m.fuel} L</td>
                  <td className="px-4 py-2.5">{m.co2} kg</td>
                  <td className="px-4 py-2.5">{m.emptyKm} km</td>
                  <td className="px-4 py-2.5">{m.utilization}%</td>
                  <td className="px-4 py-2.5">{m.failed}</td>
                  <td className="px-4 py-2.5">{m.runtime}s</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>
    </div>
  );
}
