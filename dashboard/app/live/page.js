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
    body: "Breakdown and cloud-outage events push a note onto the page and highlight the affected truck's contract-net bidding in real time.",
  },
];

export default function LivePage() {
  return (
    <div>
      <Section index="1" title="Live view">
        <p className="text-sm text-muted max-w-2xl">
          Not built yet. Everything else in this summary reads pre-generated
          benchmark output from the repository; live mode would connect this
          same UI to a running simulation instead.
        </p>
      </Section>

      <div className="border border-ink bg-panel p-6 mb-10">
        <div className="mono text-xs text-muted">status</div>
        <div className="mt-1 text-sm text-ink">No live connection configured</div>
        <div className="mt-1 text-xs text-muted max-w-md">
          This page will activate once a simulation backend is running and
          reachable — see the plan below.
        </div>
      </div>

      <Section index="2" title="Planned architecture">
        <ol className="border border-ink divide-y divide-rule">
          {steps.map((s, i) => (
            <li key={s.title} className="p-4 flex gap-4">
              <span className="mono text-xs text-muted pt-0.5 w-5 shrink-0">{i + 1}.</span>
              <div>
                <div className="text-sm text-ink">{s.title}</div>
                <div className="text-xs text-muted mt-1 max-w-xl leading-relaxed">{s.body}</div>
              </div>
            </li>
          ))}
        </ol>
      </Section>
    </div>
  );
}
