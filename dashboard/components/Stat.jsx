export default function Stat({ label, value, unit, sub }) {
  return (
    <div className="border-t border-ink pt-2">
      <div className="mono text-2xl text-ink leading-none">
        {value}
        {unit && <span className="text-sm text-muted ml-1">{unit}</span>}
      </div>
      <div className="mt-1.5 text-xs text-muted">{label}</div>
      {sub && <div className="mt-0.5 text-[11px] text-muted mono">{sub}</div>}
    </div>
  );
}
