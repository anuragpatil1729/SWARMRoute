import Link from "next/link";
import Stat from "../components/Stat";
import Section from "../components/Section";
import MeshHero from "../components/MeshHero";
import { getMethodComparison, getDisruptionScenarios } from "../lib/data";

export default function OverviewPage() {
  const methods = getMethodComparison();
  const scenarios = getDisruptionScenarios();

  const ruleBased = methods.find((m) => m.method === "Rule-Based Decentralized");
  const orTools = methods.find((m) => m.method === "OR-Tools (Static)");
  const ppo = methods.find((m) => m.method === "PPO Adaptive Agent");

  const scenarioF = scenarios.find((s) => s.key === "F");
  const swarmF = scenarioF?.methods.find((m) => m.method === "Rule-Based SWARMRoute");
  const staticF = scenarioF?.methods.find((m) => m.method === "Static OR-Tools");

  return (
    <div>
      <div className="grid grid-cols-1 md:grid-cols-[1.1fr_1fr] gap-8 items-center mb-12">
        <div>
          <h1 className="text-3xl md:text-[2.15rem] leading-tight font-semibold text-white max-w-lg">
            The fleet keeps moving when the network doesn&apos;t.
          </h1>
          <p className="mt-4 text-sm text-muted max-w-md leading-relaxed">
            SWARMRoute simulates a decentralized delivery fleet that recovers
            from breakdowns, traffic, and cloud outages by bidding on stranded
            orders over a truck-to-truck mesh network — no central server
            required. This console reads the simulation&apos;s own benchmark
            output: nothing here is live yet.
          </p>
          <div className="mt-6 flex gap-3">
            <Link
              href="/benchmarks"
              className="px-4 py-2 text-sm bg-accent text-bg font-medium hover:opacity-90 transition-opacity"
            >
              View method comparison
            </Link>
            <Link
              href="/disruptions"
              className="px-4 py-2 text-sm border border-border text-white hover:border-muted transition-colors"
            >
              Disruption scenarios
            </Link>
          </div>
        </div>
        <div className="bg-panel border border-border h-[260px] flex items-center justify-center">
          <div className="w-full h-full p-2">
            <MeshHero />
          </div>
        </div>
      </div>

      <Section>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
          <Stat
            label="Recovery success (F)"
            value={swarmF?.success ?? "—"}
            unit="%"
            tickColor="#4dd9c4"
            sub={`vs ${staticF?.success ?? "—"}% static OR-Tools`}
          />
          <Stat
            label="Fleet at 25 trucks"
            value={ruleBased ? ruleBased.utilization : "—"}
            unit="% util"
            tickColor="#f5a623"
            sub="single-scenario run, seed 101"
          />
          <Stat
            label="Mesh recovery time"
            value="1–4"
            unit="ms"
            tickColor="#818cf8"
            sub="contract-net bid to reassignment"
          />
          <Stat
            label="Tests passing"
            value="59"
            unit="/ 59"
            tickColor="#4dd9c4"
            sub="physics, mesh, RL, recovery"
          />
        </div>
      </Section>

      <Section
        title="Where the resilience comes from"
        description="Static routing is efficient in calm conditions but brittle under disruption. SWARMRoute trades a little efficiency for the ability to keep delivering when a truck goes down or the cloud connection drops."
      >
        <div className="border border-border">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-muted border-b border-border">
                <th className="font-normal px-4 py-3">Method</th>
                <th className="font-normal px-4 py-3">Success</th>
                <th className="font-normal px-4 py-3">On-time</th>
                <th className="font-normal px-4 py-3">Distance</th>
                <th className="font-normal px-4 py-3">Fuel</th>
              </tr>
            </thead>
            <tbody className="mono">
              {methods.map((m) => (
                <tr key={m.method} className="border-b border-border last:border-0">
                  <td className="px-4 py-3 text-white">{m.method}</td>
                  <td className="px-4 py-3">{m.success}%</td>
                  <td className="px-4 py-3">{m.onTime}%</td>
                  <td className="px-4 py-3">{m.distance} km</td>
                  <td className="px-4 py-3">{m.fuel} L</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="mt-3 text-xs text-muted">
          Full breakdown, including CO₂ and utilization, on the{" "}
          <Link href="/benchmarks" className="text-accent hover:underline">
            method comparison
          </Link>{" "}
          page.
        </div>
      </Section>

      <Section
        title="Read next"
        className="mb-0"
      >
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-px bg-border border border-border">
          <Link href="/disruptions" className="bg-panel hover:bg-panel2 p-5 transition-colors">
            <div className="text-sm font-medium text-white">Disruption scenarios</div>
            <div className="mt-1 text-xs text-muted">
              Eight scripted failure scenarios, A through H, compared across methods.
            </div>
          </Link>
          <Link href="/ppo-training" className="bg-panel hover:bg-panel2 p-5 transition-colors">
            <div className="text-sm font-medium text-white">PPO training</div>
            <div className="mt-1 text-xs text-muted">
              Reward curve, ablation study, and why the heuristic still wins.
            </div>
          </Link>
          <Link href="/routes" className="bg-panel hover:bg-panel2 p-5 transition-colors">
            <div className="text-sm font-medium text-white">Route map</div>
            <div className="mt-1 text-xs text-muted">
              The actual OR-Tools solution plotted over the Solomon C101 customers.
            </div>
          </Link>
        </div>
      </Section>
    </div>
  );
}
