export default function Section({ title, description, children, className = "" }) {
  return (
    <section className={`mb-10 ${className}`}>
      {title && (
        <div className="mb-4">
          <h2 className="text-base font-semibold text-white">{title}</h2>
          {description && (
            <p className="mt-1 text-sm text-muted max-w-2xl">{description}</p>
          )}
        </div>
      )}
      {children}
    </section>
  );
}
