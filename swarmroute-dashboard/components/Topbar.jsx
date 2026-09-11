export default function Topbar() {
  return (
    <div className="flex items-center justify-between border-b border-border bg-bg px-6 py-2.5 text-xs mono text-muted">
      <div className="flex items-center gap-4">
        <span className="inline-flex items-center gap-1.5">
          <span className="h-1.5 w-1.5 rounded-full bg-accent inline-block" />
          simulation data · not connected to a live fleet
        </span>
      </div>
      <div className="hidden sm:flex items-center gap-4">
        <span>dataset: C101 / R101 / RC101</span>
        <span>PPO: Stable-Baselines3</span>
      </div>
    </div>
  );
}
