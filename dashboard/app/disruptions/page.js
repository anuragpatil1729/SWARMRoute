import Section from "../../components/Section";
import ScenarioCard from "../../components/ScenarioCard";
import { getDisruptionScenarios } from "../../lib/data";

export default function DisruptionsPage() {
  const scenarios = getDisruptionScenarios();

  return (
    <div>
      <Section index="1" title="Disruption scenarios">
        <p className="text-sm text-muted max-w-2xl">
          Eight scripted failure scenarios (A–H), each replayed against
          Static OR-Tools, the rule-based decentralized SwarmRoute
          controller, and the PPO agent. Bars show delivery success; the gap
          between static and rule-based is the resilience the mesh network
          buys you.
        </p>
      </Section>

      <Section index="2" title="Legend">
        <div className="flex flex-wrap gap-x-6 gap-y-2 text-xs mono">
          <span className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 inline-block" style={{ background: "#61635a" }} />
            Static OR-Tools
          </span>
          <span className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 inline-block" style={{ background: "#2e6b34" }} />
            Rule-Based SwarmRoute
          </span>
          <span className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 inline-block" style={{ background: "#3d5566" }} />
            PPO-SwarmRoute
          </span>
        </div>
      </Section>

      <Section index="3" title="Results, by scenario">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
          {scenarios.map((s) => (
            <ScenarioCard key={s.key} scenario={s} />
          ))}
        </div>
      </Section>

      <Section index="4" title="Reading the results">
        <ul className="text-sm text-muted space-y-2 list-disc pl-5 max-w-2xl">
          <li>
            <span className="text-ink">Scenarios A, B, E, F</span> involve
            truck breakdowns — this is where the rule-based controller pulls
            ahead, absorbing stranded orders via peer-to-peer bidding.
          </li>
          <li>
            <span className="text-ink">Scenarios C and D</span> (traffic,
            cloud outage alone) don&apos;t strand any cargo, so all three
            methods land at the same success rate.
          </li>
          <li>
            <span className="text-ink">Scenarios G and H</span> are demand
            and cascading-failure stress tests where even the decentralized
            controller can&apos;t fully recover — a ceiling set by fleet
            capacity, not coordination strategy.
          </li>
        </ul>
      </Section>
    </div>
  );
}
