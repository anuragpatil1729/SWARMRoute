export default function Section({ index, title, description, children, className = "" }) {
  return (
    <section className={`mb-8 ${className}`}>
      {title && (
        <div className="mb-4 pb-2 border-b border-slate-200 flex items-baseline gap-3">
          {index && <span className="font-mono text-xs text-slate-400 font-semibold">{index}</span>}
          <h2 className="text-base font-bold text-slate-900 tracking-tight">{title}</h2>
        </div>
      )}
      {description && (
        <p className="mb-4 text-xs text-slate-500 max-w-2xl leading-relaxed">
          {description}
        </p>
      )}
      {children}
    </section>
  );
}
