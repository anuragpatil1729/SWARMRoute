export default function Stat({ label, value, unit, sub }) {
  return (
    <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm hover:border-slate-300 transition-colors">
      <div className="text-2xl font-bold font-mono text-slate-900 leading-none">
        {value}
        {unit && <span className="text-sm font-normal text-slate-500 ml-1">{unit}</span>}
      </div>
      <div className="mt-2 text-xs font-medium text-slate-500 uppercase tracking-wider">{label}</div>
      {sub && <div className="mt-1 text-[11px] text-slate-400 font-mono">{sub}</div>}
    </div>
  );
}
