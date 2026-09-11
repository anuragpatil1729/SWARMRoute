const methodColor = {
  "Static OR-Tools": "#94a3b8",
  "Rule-Based SWARMRoute": "#16a34a",
  "PPO-SWARMRoute": "#2563eb",
  "Autonomous SWARMRoute": "#2563eb",
};

export default function ScenarioCard({ scenario }) {
  const best = Math.max(...scenario.methods.map((m) => m.success));

  return (
    <div className="border border-slate-200 bg-white rounded-xl shadow-sm overflow-hidden">
      <div className="px-4 py-3 border-b border-slate-100 flex items-baseline justify-between bg-slate-50/50">
        <div>
          <span className="font-mono text-xs text-blue-600 font-bold mr-2">{scenario.key}</span>
          <span className="text-sm font-semibold text-slate-800">{scenario.name}</span>
        </div>
        <span className="text-[11px] text-slate-400 font-mono">
          {scenario.disruptions} disruption{scenario.disruptions === 1 ? "" : "s"}
        </span>
      </div>
      <div className="px-4 py-4 space-y-3">
        {scenario.methods.map((m) => {
          const displayLabel = m.method.replace("PPO-", "Autonomous ");
          return (
            <div key={m.method}>
              <div className="flex justify-between text-xs mb-1 font-mono">
                <span className={m.success === best ? "font-bold text-slate-900" : "text-slate-500"}>
                  {displayLabel}
                </span>
                <span className="font-semibold" style={{ color: methodColor[m.method] || "#2563eb" }}>
                  {m.success}%
                </span>
              </div>
              <div className="h-2 bg-slate-100 rounded-full overflow-hidden w-full">
                <div
                  className="h-full rounded-full transition-all"
                  style={{
                    width: `${m.success}%`,
                    background: methodColor[m.method] || "#2563eb",
                  }}
                />
              </div>
            </div>
          );
        })}
      </div>
      <div className="px-4 py-2.5 border-t border-slate-100 text-[11px] text-slate-400 font-mono flex justify-between bg-slate-50/30">
        <span>Failed: {scenario.methods.map((m) => m.failed).join(" / ")}</span>
        <span>Recovery: {Math.max(...scenario.methods.map((m) => m.recovery * 1000)).toFixed(1)}ms</span>
      </div>
    </div>
  );
}
