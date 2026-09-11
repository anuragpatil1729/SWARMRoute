import Section from "../../components/Section";

const steps = [
  {
    title: "Expose the simulation loop",
    body: "Wrap FleetSimulationEnvironment's step loop in a small FastAPI/WebSocket service inside the Python repo, emitting one frame per simulated tick (truck positions, order states, mesh messages).",
  },
  {
    title: "Stream frames to the browser",
    body: "This dashboard opens a WebSocket to that service and replaces the static JSON in lib/data.js with incoming frames, keyed by simulation clock.",
  },
  {
    title: "Animate the route map",
    body: "RouteMap already renders trucks and customers on an SVG canvas — live mode reuses it, moving truck markers along their route each tick instead of drawing a static polyline.",
  },
  {
    title: "Surface disruptions as they happen",
    body: "Breakdown and cloud-outage events push a toast onto the console and highlight the affected truck's contract-net bidding in real time.",
  },
];

export default function LivePage() {
  return (
    <div>
      <h1 className="text-2xl font-semibold text-white mb-1">Live view</h1>
      <p className="text-sm text-muted mb-8 max-w-2xl">
        Not built yet. Everything else in this console reads pre-generated
        benchmark output from the repo; live mode would connect this same UI
        to a running simulation instead.
      </p>

      <div className="border border-border bg-panel p-8 mb-10 flex items-center gap-4">
        <span className="h-2 w-2 rounded-full bg-warn inline-block shrink-0" />
        <div>
          <div className="text-sm text-white">No live connection configured</div>
          <div className="text-xs text-muted mt-0.5">
            This page will activate once a simulation backend is running and
            reachable — see the plan below.
          </div>
        </div>
      </div>

      <Section title="Planned architecture">
        <div className="border border-border divide-y divide-border">
          {steps.map((s, i) => (
            <div key={s.title} className="p-4 flex gap-4">
              <span className="mono text-xs text-muted pt-0.5 w-5 shrink-0">
                {i + 1}
              </span>
              <div>
                <div className="text-sm text-white">{s.title}</div>
                <div className="text-xs text-muted mt-1 max-w-xl leading-relaxed">
                  {s.body}
                </div>
              </div>
            </div>
          ))}
        </div>
      </Section>
    </div>
  );
}
