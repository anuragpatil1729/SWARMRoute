const methodColor = {
  "Static OR-Tools": "#5b6779",
  "Rule-Based SWARMRoute": "#4dd9c4",
  "PPO-SWARMRoute": "#818cf8",
};

export default function ScenarioCard({ scenario }) {
  const best = Math.max(...scenario.methods.map((m) => m.success));

  return (
    <div className="border border-border bg-panel">
      <div className="px-4 py-3 border-b border-border flex items-baseline justify-between">
        <div>
          <span className="mono text-xs text-muted mr-2">{scenario.key}</span>
          <span className="text-sm text-white">{scenario.name}</span>
        </div>
        <span className="text-[11px] text-muted mono">
          {scenario.disruptions} disruption{scenario.disruptions === 1 ? "" : "s"}
        </span>
      </div>
      <div className="px-4 py-4 space-y-3">
        {scenario.methods.map((m) => (
          <div key={m.method}>
            <div className="flex justify-between text-xs mb-1">
              <span
                className="mono"
                style={{ color: m.success === best ? "#fff" : "#8b93a7" }}
              >
                {m.method}
              </span>
              <span className="mono" style={{ color: methodColor[m.method] }}>
                {m.success}%
              </span>
            </div>
            <div className="h-1.5 bg-panel2 w-full">
              <div
                className="h-1.5"
                style={{
                  width: `${m.success}%`,
                  background: methodColor[m.method] || "#5b6779",
                }}
              />
            </div>
          </div>
        ))}
      </div>
      <div className="px-4 py-2.5 border-t border-border text-[11px] text-muted mono flex justify-between">
        <span>failed: {scenario.methods.map((m) => m.failed).join(" / ")}</span>
        <span>recovery: {Math.max(...scenario.methods.map((m) => m.recovery * 1000)).toFixed(1)}ms</span>
      </div>
    </div>
  );
}
