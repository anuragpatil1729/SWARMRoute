"use client";

import { useMemo, useState } from "react";

const PALETTE = [
  "#2e6b34", "#3d5566", "#8a6d1f", "#7a9c5e", "#61635a",
  "#5c7a8a", "#9c7a2e", "#4a7a4f", "#6b5c8a", "#2e6b34",
];

export default function LiveRouteMap({
  customers = [],
  depot = { x: 40, y: 50 },
  routes = {},
  recoveryRoutes = {},
  vehicles = [],
  trafficEdges = [],
  selectedVehicleId = null,
  onSelectVehicle = null,
  onSelectOrder = null,
}) {
  const [activeTruck, setActiveTruck] = useState(null);

  const effectiveSelected = selectedVehicleId || activeTruck;

  const { minX, maxX, minY, maxY, coordsById } = useMemo(() => {
    const map = {};
    if (depot) map[0] = depot;

    const xs = [depot?.x ?? 40];
    const ys = [depot?.y ?? 50];

    customers.forEach((c) => {
      map[c.id] = c;
      xs.push(c.x);
      ys.push(c.y);
    });

    vehicles.forEach((v) => {
      if (typeof v.x === "number" && typeof v.y === "number") {
        xs.push(v.x);
        ys.push(v.y);
      }
    });

    return {
      minX: Math.min(...xs),
      maxX: Math.max(...xs),
      minY: Math.min(...ys),
      maxY: Math.max(...ys),
      coordsById: map,
    };
  }, [customers, depot, vehicles]);

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
          {/* Axes box */}
          <rect x={pad} y={pad} width={w - pad * 2} height={h - pad * 2} fill="none" stroke="#181a16" strokeWidth="1" />
          {Array.from({ length: gridLinesX + 1 }).map((_, i) => {
            const x = pad + (i / gridLinesX) * (w - pad * 2);
            return <line key={`gx-${i}`} x1={x} y1={pad} x2={x} y2={h - pad} stroke="#e9e9e0" strokeWidth="1" />;
          })}
          {Array.from({ length: gridLinesY + 1 }).map((_, i) => {
            const y = pad + (i / gridLinesY) * (h - pad * 2);
            return <line key={`gy-${i}`} x1={pad} y1={y} x2={w - pad} y2={y} stroke="#e9e9e0" strokeWidth="1" />;
          })}

          {/* Traffic Congestion Edges */}
          {trafficEdges.map((te, idx) => {
            const c1 = coordsById[te.u];
            const c2 = coordsById[te.v];
            if (!c1 || !c2) return null;
            return (
              <line
                key={`traffic-${idx}`}
                x1={scaleX(c1.x)}
                y1={scaleY(c1.y)}
                x2={scaleX(c2.x)}
                y2={scaleY(c2.y)}
                stroke="#a13a2e"
                strokeWidth="4"
                strokeOpacity="0.6"
                strokeDasharray="4 2"
              />
            );
          })}

          {/* Active Routes */}
          {Object.entries(routes).map(([truckId, stopIds], idx) => {
            const color = PALETTE[idx % PALETTE.length];
            const dimmed = effectiveSelected && effectiveSelected !== truckId;
            const pts = stopIds
              .map((id) => coordsById[id])
              .filter(Boolean)
              .map((c) => `${scaleX(c.x)},${scaleY(c.y)}`)
              .join(" ");

            if (!pts) return null;
            return (
              <polyline
                key={`route-${truckId}`}
                points={pts}
                fill="none"
                stroke={color}
                strokeWidth={dimmed ? 1 : 1.75}
                opacity={dimmed ? 0.15 : 0.85}
                strokeLinejoin="round"
              />
            );
          })}

          {/* Recovery Reassigned Routes (Dashed) */}
          {Object.entries(recoveryRoutes).map(([truckId, stopIds], idx) => {
            const pts = stopIds
              .map((id) => coordsById[id])
              .filter(Boolean)
              .map((c) => `${scaleX(c.x)},${scaleY(c.y)}`)
              .join(" ");

            if (!pts) return null;
            return (
              <polyline
                key={`rec-route-${truckId}`}
                points={pts}
                fill="none"
                stroke="#8a6d1f"
                strokeWidth="2.5"
                strokeDasharray="5 3"
                opacity={0.9}
                strokeLinejoin="round"
              />
            );
          })}

          {/* Customers Nodes */}
          {customers.map((c) => {
            const isDelivered = c.status === "DELIVERED";
            return (
              <g
                key={`cust-${c.id}`}
                className="cursor-pointer"
                onClick={() => onSelectOrder && onSelectOrder(c.order_id || `ORD_${c.id}`)}
              >
                <circle
                  cx={scaleX(c.x)}
                  cy={scaleY(c.y)}
                  r={isDelivered ? 3 : 2.5}
                  fill={isDelivered ? "#2e6b34" : "#61635a"}
                />
                <title>{`Customer #${c.id} (Demand: ${c.demand}kg)`}</title>
              </g>
            );
          })}

          {/* Depot */}
          {depot && (
            <g>
              <rect
                x={scaleX(depot.x) - 5}
                y={scaleY(depot.y) - 5}
                width={10}
                height={10}
                fill="#a13a2e"
              />
              <text
                x={scaleX(depot.x) + 7}
                y={scaleY(depot.y) + 3}
                fontSize="9"
                fontFamily="ui-monospace, monospace"
                fill="#181a16"
              >
                DEPOT
              </text>
            </g>
          )}

          {/* Moving Vehicles */}
          {vehicles.map((v, idx) => {
            const isBroken = v.status === "BROKEN_DOWN";
            const color = isBroken ? "#a13a2e" : PALETTE[idx % PALETTE.length];
            const isSelected = effectiveSelected === v.id;
            const vx = scaleX(v.x);
            const vy = scaleY(v.y);

            return (
              <g
                key={`veh-${v.id}`}
                className="cursor-pointer"
                onClick={() => {
                  if (onSelectVehicle) onSelectVehicle(v.id);
                  setActiveTruck(activeTruck === v.id ? null : v.id);
                }}
              >
                {/* Ping animation or selection ring */}
                {isSelected && (
                  <circle cx={vx} cy={vy} r={11} fill="none" stroke={color} strokeWidth="1.5" strokeDasharray="3 2" />
                )}
                {/* Truck marker */}
                <circle
                  cx={vx}
                  cy={vy}
                  r={isBroken ? 6 : 5}
                  fill={isBroken ? "#a13a2e" : color}
                  stroke="#fbfbf8"
                  strokeWidth="1.5"
                />
                {isBroken ? (
                  <text x={vx - 3} y={vy + 3} fontSize="8" fill="#ffffff" fontWeight="bold">!</text>
                ) : null}
                <text
                  x={vx + 7}
                  y={vy + 3}
                  fontSize="9"
                  fontFamily="ui-monospace, monospace"
                  fontWeight="600"
                  fill={isBroken ? "#a13a2e" : "#181a16"}
                >
                  {v.id.replace("TRUCK_", "T")}
                </text>
              </g>
            );
          })}

          {/* Legend Box */}
          <rect x={w - pad - 148} y={pad + 6} width={142} height={42} fill="#fbfbf8" stroke="#181a16" strokeWidth="1" />
          <rect x={w - pad - 140} y={pad + 12} width={7} height={7} fill="#a13a2e" />
          <text x={w - pad - 128} y={pad + 18} fontSize="9" fontFamily="ui-monospace, monospace" fill="#181a16">
            Depot
          </text>
          <circle cx={w - pad - 136} cy={pad + 28} r={3} fill="#2e6b34" />
          <text x={w - pad - 128} y={pad + 31} fontSize="9" fontFamily="ui-monospace, monospace" fill="#181a16">
            Delivered
          </text>
          <circle cx={w - pad - 68} cy={pad + 28} r={3} fill="#61635a" />
          <text x={w - pad - 60} y={pad + 31} fontSize="9" fontFamily="ui-monospace, monospace" fill="#181a16">
            Pending
          </text>
        </svg>
      </div>

      {/* Fleet Filter Bar */}
      <div className="mt-3 flex flex-wrap items-center gap-2 mono text-xs">
        <button
          onClick={() => {
            setActiveTruck(null);
            if (onSelectVehicle) onSelectVehicle(null);
          }}
          className={`px-2.5 py-1 border ${
            !effectiveSelected ? "border-ink bg-panel2 text-ink font-semibold" : "border-rule text-muted hover:border-ink"
          }`}
        >
          All Fleet
        </button>
        {vehicles.map((v, idx) => {
          const isBroken = v.status === "BROKEN_DOWN";
          const color = isBroken ? "#a13a2e" : PALETTE[idx % PALETTE.length];
          const isSelected = effectiveSelected === v.id;
          return (
            <button
              key={v.id}
              onClick={() => {
                const nextId = isSelected ? null : v.id;
                setActiveTruck(nextId);
                if (onSelectVehicle) onSelectVehicle(nextId);
              }}
              className="flex items-center gap-1.5 px-2 py-1 border transition-colors"
              style={{
                borderColor: isSelected ? color : "#c9c9bc",
                backgroundColor: isSelected ? "#e9e9e0" : "transparent",
                color: isSelected ? "#181a16" : "#61635a",
              }}
            >
              <span className="w-2 h-2 inline-block rounded-full" style={{ background: color }} />
              <span className="font-semibold">{v.id.replace("TRUCK_", "T")}</span>
              <span className="text-[10px] text-muted">
                {isBroken ? "(FAULT)" : `${v.speed_kmh}km/h`}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
