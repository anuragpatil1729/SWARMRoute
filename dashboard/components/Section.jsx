export default function Section({ index, title, description, children, className = "" }) {
  return (
    <section className={`mb-12 ${className}`}>
      {title && (
        <div className="mb-4 pb-2 border-b border-ink flex items-baseline gap-3">
          {index && <span className="mono text-xs text-muted">§{index}</span>}
          <h2 className="text-base font-semibold text-ink">{title}</h2>
        </div>
      )}
      {description && (
        <p className="mb-4 text-sm text-muted max-w-2xl leading-relaxed">
          {description}
        </p>
      )}
      {children}
    </section>
  );
}
