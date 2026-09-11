export default function Stat({ label, value, unit, tickColor = "#4dd9c4", sub }) {
  return (
    <div className="tick" style={{ "--tick-color": tickColor }}>
      <div className="text-[11px] uppercase tracking-wide text-muted mono">
        {label}
      </div>
      <div className="mt-1 text-2xl font-semibold text-white mono">
        {value}
        {unit && <span className="text-sm text-muted ml-1">{unit}</span>}
      </div>
      {sub && <div className="mt-0.5 text-xs text-muted">{sub}</div>}
    </div>
  );
}
