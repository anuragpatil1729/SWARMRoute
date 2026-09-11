"use client";

import { useMemo, useState } from "react";

const PALETTE = [
  "#4dd9c4", "#f5a623", "#818cf8", "#fb7185", "#34d399",
  "#facc15", "#60a5fa", "#f472b6", "#a78bfa", "#2dd4bf",
];

export default function RouteMap({ customers, depot, routes }) {
  const [activeTruck, setActiveTruck] = useState(null);

  const { minX, maxX, minY, maxY } = useMemo(() => {
    const xs = customers.map((c) => c.x);
    const ys = customers.map((c) => c.y);
    return {
      minX: Math.min(...xs),
      maxX: Math.max(...xs),
      minY: Math.min(...ys),
      maxY: Math.max(...ys),
    };
  }, [customers]);

  const pad = 6;
  const w = 600;
  const h = 420;
  const scaleX = (x) =>
    pad + ((x - minX) / (maxX - minX || 1)) * (w - pad * 2);
  const scaleY = (y) =>
    h - pad - ((y - minY) / (maxY - minY || 1)) * (h - pad * 2);

  return (
    <div>
      <svg viewBox={`0 0 ${w} ${h}`} className="w-full border border-border bg-panel">
        {routes.map((r, idx) => {
          const color = PALETTE[idx % PALETTE.length];
          const dimmed = activeTruck && activeTruck !== r.truck;
          const points = r.path.map((c) => `${scaleX(c.x)},${scaleY(c.y)}`).join(" ");
          return (
            <polyline
              key={r.truck}
              points={points}
              fill="none"
              stroke={color}
              strokeWidth={dimmed ? 1 : 2}
              opacity={dimmed ? 0.15 : 0.9}
              strokeLinejoin="round"
            />
          );
        })}
        {customers.map((c) => (
          <circle
            key={c.id}
            cx={scaleX(c.x)}
            cy={scaleY(c.y)}
            r={c.id === 0 ? 0 : 2}
            fill="#5b6779"
          />
        ))}
        {depot && (
          <g>
            <rect
              x={scaleX(depot.x) - 5}
              y={scaleY(depot.y) - 5}
              width={10}
              height={10}
              fill="#f5a623"
            />
          </g>
        )}
      </svg>

      <div className="mt-4 flex flex-wrap gap-x-4 gap-y-2 text-xs mono">
        <button
          onClick={() => setActiveTruck(null)}
          className={`px-2 py-1 border ${
            activeTruck === null ? "border-accent text-white" : "border-border text-muted"
          }`}
        >
          all trucks
        </button>
        {routes.map((r, idx) => (
          <button
            key={r.truck}
            onClick={() => setActiveTruck(activeTruck === r.truck ? null : r.truck)}
            className="flex items-center gap-1.5 px-2 py-1 border"
            style={{
              borderColor: activeTruck === r.truck ? PALETTE[idx % PALETTE.length] : "#232834",
              color: activeTruck === r.truck ? "#fff" : "#8b93a7",
            }}
          >
            <span
              className="w-2 h-2 inline-block"
              style={{ background: PALETTE[idx % PALETTE.length] }}
            />
            {r.truck.replace("TRUCK_", "T")}
            <span className="text-muted">· {r.stops.length - 2} stops</span>
          </button>
        ))}
      </div>
    </div>
  );
}
