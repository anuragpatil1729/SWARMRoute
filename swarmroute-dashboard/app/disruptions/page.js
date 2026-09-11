import Section from "../../components/Section";
import ScenarioCard from "../../components/ScenarioCard";
import { getDisruptionScenarios } from "../../lib/data";

export default function DisruptionsPage() {
  const scenarios = getDisruptionScenarios();

  return (
    <div>
      <h1 className="text-2xl font-semibold text-white mb-1">Disruption scenarios</h1>
      <p className="text-sm text-muted mb-8 max-w-2xl">
        Eight scripted failure scenarios (A–H), each replayed against Static
        OR-Tools, the rule-based decentralized SWARMRoute controller, and the
        PPO agent. Bars show delivery success; the gap between static and
        rule-based is the resilience the mesh network buys you.
      </p>

      <Section
        title="Legend"
        className="mb-8"
      >
        <div className="flex flex-wrap gap-x-6 gap-y-2 text-xs mono">
          <span className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 inline-block" style={{ background: "#5b6779" }} />
            Static OR-Tools
          </span>
          <span className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 inline-block" style={{ background: "#4dd9c4" }} />
            Rule-Based SWARMRoute
          </span>
          <span className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 inline-block" style={{ background: "#818cf8" }} />
            PPO-SWARMRoute
          </span>
        </div>
      </Section>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
        {scenarios.map((s) => (
          <ScenarioCard key={s.key} scenario={s} />
        ))}
      </div>

      <Section title="Reading the results" className="mt-10">
        <ul className="text-sm text-muted space-y-2 list-disc pl-5 max-w-2xl">
          <li>
            <span className="text-white">Scenarios A, B, E, F</span> involve
            truck breakdowns — this is where the rule-based controller pulls
            ahead, absorbing stranded orders via peer-to-peer bidding.
          </li>
          <li>
            <span className="text-white">Scenarios C and D</span> (traffic,
            cloud outage alone) don&apos;t strand any cargo, so all three
            methods land at the same success rate.
          </li>
          <li>
            <span className="text-white">Scenarios G and H</span> are demand
            and cascading-failure stress tests where even the decentralized
            controller can&apos;t fully recover — a ceiling set by fleet
            capacity, not coordination strategy.
          </li>
        </ul>
      </Section>
    </div>
  );
}
