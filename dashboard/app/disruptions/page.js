import ScenarioCard from "../../components/ScenarioCard";
import { getDisruptionScenarios } from "../../lib/data";

export default function DisruptionsPage() {
  const scenarios = getDisruptionScenarios();

  return (
    <div className="space-y-6">
      <div className="border border-slate-200 bg-white p-5 rounded-xl shadow-sm">
        <h2 className="text-xl font-bold text-slate-900">
          Disruption & Resilience Replay
        </h2>
        <p className="text-xs text-slate-500 mt-1">
          Evaluating autonomous peer-to-peer resilience across eight operational failure scenarios (A–H) against static baselines.
        </p>
      </div>

      <div className="border border-slate-200 bg-white p-4 rounded-xl shadow-sm">
        <div className="flex flex-wrap gap-x-6 gap-y-2 text-xs font-mono">
          <span className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full inline-block bg-slate-400" />
            <span className="text-slate-600">Static OR-Tools Baseline</span>
          </span>
          <span className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full inline-block bg-emerald-600" />
            <span className="text-slate-600">Rule-Based Mesh SWARMRoute</span>
          </span>
          <span className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full inline-block bg-blue-600" />
            <span className="text-slate-600">Autonomous Resilient Agent</span>
          </span>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
        {scenarios.map((s) => (
          <ScenarioCard key={s.key} scenario={s} />
        ))}
      </div>

      <div className="border border-slate-200 bg-white p-5 rounded-xl shadow-sm space-y-2">
        <h3 className="text-sm font-bold text-slate-800">Key Operational Insights</h3>
        <ul className="text-xs text-slate-600 space-y-2 list-disc pl-5 max-w-2xl leading-relaxed">
          <li>
            <span className="font-semibold text-slate-800">Scenarios A, B, E, F:</span> Vehicle mechanical failure and breakdown recovery. Decentralized contract-net auctions dynamically re-route stranded packages to neighbor trucks without human dispatch intervention.
          </li>
          <li>
            <span className="font-semibold text-slate-800">Scenarios C & D:</span> High traffic congestion and cloud infrastructure outages. Ad-hoc vehicle mesh network maintains continuous communication and route synchronization.
          </li>
          <li>
            <span className="font-semibold text-slate-800">Scenarios G & H:</span> Demand spikes and cascading multiple failures testing physical fleet payload limits.
          </li>
        </ul>
      </div>
    </div>
  );
}
