"use client";

import { useMemo, useState } from "react";

const PALETTE = [
  "#2e6b34", "#3d5566", "#8a6d1f", "#7a9c5e", "#61635a",
  "#5c7a8a", "#9c7a2e", "#4a7a4f", "#6b5c8a", "#2e6b34",
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

  const pad = 24;
  const w = 620;
  const h = 420;
  const scaleX = (x) => pad + ((x - minX) / (maxX - minX || 1)) * (w - pad * 2);
  const scaleY = (y) => h - pad - ((y - minY) / (maxY - minY || 1)) * (h - pad * 2);

  const gridLinesX = 6;
  const gridLinesY = 5;

  return (
    <div>
      <div className="border border-ink bg-panel p-3">
        <svg viewBox={`0 0 ${w} ${h}`} className="w-full">
          {/* axes box */}
          <rect x={pad} y={pad} width={w - pad * 2} height={h - pad * 2} fill="none" stroke="#181a16" strokeWidth="1" />
          {Array.from({ length: gridLinesX + 1 }).map((_, i) => {
            const x = pad + (i / gridLinesX) * (w - pad * 2);
            return <line key={`gx-${i}`} x1={x} y1={pad} x2={x} y2={h - pad} stroke="#e9e9e0" strokeWidth="1" />;
          })}
          {Array.from({ length: gridLinesY + 1 }).map((_, i) => {
            const y = pad + (i / gridLinesY) * (h - pad * 2);
            return <line key={`gy-${i}`} x1={pad} y1={y} x2={w - pad} y2={y} stroke="#e9e9e0" strokeWidth="1" />;
          })}

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
                strokeWidth={dimmed ? 1 : 1.75}
                opacity={dimmed ? 0.15 : 0.95}
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
              fill="#61635a"
            />
          ))}
          {depot && (
            <rect
              x={scaleX(depot.x) - 5}
              y={scaleY(depot.y) - 5}
              width={10}
              height={10}
              fill="#a13a2e"
            />
          )}
          {/* boxed legend, matplotlib-style */}
          <rect x={w - pad - 122} y={pad + 6} width={116} height={20} fill="#fbfbf8" stroke="#181a16" strokeWidth="1" />
          <rect x={w - pad - 114} y={pad + 12} width={8} height={8} fill="#a13a2e" />
          <text x={w - pad - 100} y={pad + 20} fontSize="10" fontFamily="ui-monospace, monospace" fill="#181a16">
            Depot
          </text>
        </svg>
      </div>

      <div className="mt-4 flex flex-wrap gap-x-4 gap-y-2 mono text-xs">
        <button
          onClick={() => setActiveTruck(null)}
          className={`px-2 py-1 border ${
            activeTruck === null ? "border-ink text-ink" : "border-rule text-muted"
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
              borderColor: activeTruck === r.truck ? PALETTE[idx % PALETTE.length] : "#c9c9bc",
              color: activeTruck === r.truck ? "#181a16" : "#61635a",
            }}
          >
            <span className="w-2 h-2 inline-block" style={{ background: PALETTE[idx % PALETTE.length] }} />
            {r.truck.replace("TRUCK_", "T")}
            <span className="text-muted">· {r.stops.length - 2} stops</span>
          </button>
        ))}
      </div>
    </div>
  );
}
