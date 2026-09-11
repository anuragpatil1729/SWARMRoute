import Link from "next/link";
import Stat from "../components/Stat";
import Section from "../components/Section";
import MeshFigure from "../components/MeshFigure";
import { getMethodComparison, getDisruptionScenarios } from "../lib/data";

export default function OverviewPage() {
  const methods = getMethodComparison();
  const scenarios = getDisruptionScenarios();

  const ruleBased = methods.find((m) => m.method === "Rule-Based Decentralized");
  const scenarioF = scenarios.find((s) => s.key === "F");
  const swarmF = scenarioF?.methods.find((m) => m.method === "Rule-Based SWARMRoute");
  const staticF = scenarioF?.methods.find((m) => m.method === "Static OR-Tools");

  return (
    <div>
      <Section index="1" title="Abstract">
        <div className="grid grid-cols-1 md:grid-cols-[1fr_260px] gap-8">
          <p className="text-[15px] serif leading-relaxed text-ink max-w-xl">
            SwarmRoute simulates a delivery fleet that keeps moving when a
            truck breaks down or the cloud connection drops, by letting
            trucks bid on stranded orders over a peer-to-peer mesh network
            instead of waiting on a central dispatcher. This page summarizes
            the benchmark output already checked into the repository —{" "}
            <code className="mono text-sm bg-panel2 px-1">results/</code> —
            comparing that decentralized approach against static OR-Tools
            routing and a PPO reinforcement-learning agent.
          </p>
          <dl className="text-xs mono space-y-2 self-start border-l border-rule pl-4">
            <div className="flex justify-between gap-4">
              <dt className="text-muted">dataset</dt>
              <dd className="text-ink">Solomon C101</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-muted">fleet size</dt>
              <dd className="text-ink">25 trucks</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-muted">scenarios</dt>
              <dd className="text-ink">A–H</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-muted">tests passing</dt>
              <dd className="text-ink">95 / 95</dd>
            </div>
          </dl>
        </div>
      </Section>

      <Section index="2" title="Figure 1 — Mesh network topology">
        <div className="border border-ink bg-panel p-6">
          <div className="h-[220px]">
            <MeshFigure />
          </div>
        </div>
        <p className="mt-2 text-xs text-muted max-w-2xl">
          Idle links (gray) connect every truck to its neighbors; the
          highlighted path shows a stranded order being re-bid across T5 → T6
          after a breakdown, without going through the depot.
        </p>
      </Section>

      <Section index="3">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
          <Stat
            label="delivery success, scenario F"
            value={swarmF?.success ?? "—"}
            unit="%"
            sub={`vs ${staticF?.success ?? "—"}% static OR-Tools`}
          />
          <Stat
            label="fleet utilization"
            value={ruleBased ? ruleBased.utilization : "—"}
            unit="%"
            sub="single-scenario run, seed 101"
          />
          <Stat
            label="mesh recovery time"
            value="1–4"
            unit="ms"
            sub="contract-net bid to reassignment"
          />
          <Stat label="tests passing" value="95" unit="/ 95" sub="physics, mesh, RL, recovery" />
        </div>
      </Section>

      <Section
        index="4"
        title="Where the resilience comes from"
        description="Static routing is efficient in calm conditions but brittle under disruption. SwarmRoute trades a little efficiency for the ability to keep delivering when a truck goes down or the cloud connection drops."
      >
        <table className="w-full text-sm border border-ink">
          <thead>
            <tr className="text-left border-b border-ink">
              <th className="font-normal px-4 py-2.5 mono text-xs text-muted">method</th>
              <th className="font-normal px-4 py-2.5 mono text-xs text-muted">success</th>
              <th className="font-normal px-4 py-2.5 mono text-xs text-muted">on-time</th>
              <th className="font-normal px-4 py-2.5 mono text-xs text-muted">distance</th>
              <th className="font-normal px-4 py-2.5 mono text-xs text-muted">fuel</th>
            </tr>
          </thead>
          <tbody className="mono">
            {methods.map((m, i) => (
              <tr key={m.method} className={i % 2 ? "bg-panel2" : ""}>
                <td className="px-4 py-2.5 text-ink">{m.method}</td>
                <td className="px-4 py-2.5">{m.success}%</td>
                <td className="px-4 py-2.5">{m.onTime}%</td>
                <td className="px-4 py-2.5">{m.distance} km</td>
                <td className="px-4 py-2.5">{m.fuel} L</td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className="mt-3 text-xs text-muted">
          Full breakdown, including CO₂ and utilization, in{" "}
          <Link href="/benchmarks" className="text-ink underline underline-offset-2">
            method comparison
          </Link>
          .
        </div>
      </Section>

      <Section index="5" title="Contents">
        <ul className="text-sm space-y-2">
          <li>
            <Link href="/disruptions" className="text-ink underline underline-offset-2">
              Disruption scenarios
            </Link>
            <span className="text-muted"> — eight scripted failure scenarios, A through H</span>
          </li>
          <li>
            <Link href="/ppo-training" className="text-ink underline underline-offset-2">
              PPO training
            </Link>
            <span className="text-muted"> — reward curve, ablation study, and why the heuristic still wins</span>
          </li>
          <li>
            <Link href="/routes" className="text-ink underline underline-offset-2">
              Route map
            </Link>
            <span className="text-muted"> — the OR-Tools solution plotted over the Solomon C101 customers</span>
          </li>
        </ul>
      </Section>
    </div>
  );
}
