"use client";

import { useMemo } from "react";

export default function LiveMeshFigure({ mesh = {}, cloudStatus, activeRecovery, activeRoute = [] }) {
  const nodes = mesh.nodes || [];
  const links = mesh.links || [];
  const layout = useMemo(() => {
    if (!nodes.length) return null;
    const xs = nodes.map((node) => node.x);
    const ys = nodes.map((node) => node.y);
    return {
      minX: Math.min(...xs),
      maxX: Math.max(...xs),
      minY: Math.min(...ys),
      maxY: Math.max(...ys),
    };
  }, [nodes]);

  if (!layout) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-slate-400 font-mono text-xs text-center p-4">
        <span className="text-2xl mb-2">📡</span>
        <span>No active mesh radio nodes currently on the network.</span>
        <span className="text-[11px] text-slate-400 mt-1">Click &quot;Deploy Test Radio Mesh&quot; above or dispatch delivery partners to observe live topology.</span>
      </div>
    );
  }

  const width = 560;
  const height = 240;
  const pad = 44;
  const spanX = layout.maxX - layout.minX || 1;
  const spanY = layout.maxY - layout.minY || 1;
  const isIdentical = (layout.maxX === layout.minX && layout.maxY === layout.minY);

  const nodePosMap = useMemo(() => {
    const map = {};
    nodes.forEach((node, idx) => {
      if (isIdentical && nodes.length > 1) {
        const angle = (idx / nodes.length) * 2 * Math.PI - Math.PI / 2;
        map[node.id] = {
          x: width / 2 + Math.cos(angle) * 110,
          y: height / 2 + Math.sin(angle) * 60 + 10,
        };
      } else {
        map[node.id] = {
          x: pad + ((node.x - layout.minX) / spanX) * (width - pad * 2),
          y: height - pad - ((node.y - layout.minY) / spanY) * (height - pad * 2),
        };
      }
    });
    return map;
  }, [nodes, layout, spanX, spanY, isIdentical]);

  const getNodeX = (id) => nodePosMap[id]?.x ?? width / 2;
  const getNodeY = (id) => nodePosMap[id]?.y ?? height / 2;

  const routeEdges = new Set();
  if (Array.isArray(activeRoute) && activeRoute.length > 1) {
    for (let i = 0; i < activeRoute.length - 1; i++) {
      routeEdges.add(`${activeRoute[i]}--${activeRoute[i + 1]}`);
      routeEdges.add(`${activeRoute[i + 1]}--${activeRoute[i]}`);
    }
  }

  const recoveryNodes = new Set(
    [activeRecovery?.vehicle_id || activeRecovery?.broken, activeRecovery?.recovery_vehicle || activeRecovery?.winner].filter(Boolean)
  );

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-full select-none" role="img" aria-label={`Mesh topology; cloud is ${cloudStatus || "not reported"}`}>
      <rect x="0" y="0" width={width} height={height} fill="#f8fafc" rx="8" />
      <text x={pad} y="22" fontSize="11" fontWeight="600" fontFamily="ui-monospace, monospace" fill="#64748b">
        RADIO PROTOCOL: 802.11p DSRC / BLE MESH · 30 KM RF RANGE · CLOUD: {cloudStatus || "—"}
      </text>

      {/* Links */}
      {links.map((link, index) => {
        const x1 = getNodeX(link.source);
        const y1 = getNodeY(link.source);
        const x2 = getNodeX(link.target);
        const y2 = getNodeY(link.target);
        const isRoute = routeEdges.has(`${link.source}--${link.target}`);
        const recovery = recoveryNodes.has(link.source) && recoveryNodes.has(link.target);

        const strokeColor = isRoute ? "#10b981" : recovery ? "#d97706" : "#94a3b8";
        const strokeW = isRoute ? "3.5" : recovery ? "3" : "1.5";

        return (
          <g key={`${link.source}-${link.target}-${index}`}>
            <line
              x1={x1}
              y1={y1}
              x2={x2}
              y2={y2}
              stroke={strokeColor}
              strokeWidth={strokeW}
              strokeDasharray={recovery ? "6 3" : undefined}
            >
              <title>{`${link.source} ⟷ ${link.target} (${link.distance !== undefined ? `${link.distance} km` : "RF Link"})`}</title>
            </line>
            {isRoute && (
              <line
                x1={x1}
                y1={y1}
                x2={x2}
                y2={y2}
                stroke="#34d399"
                strokeWidth="1.5"
                strokeDasharray="4 4"
                className="animate-pulse"
              />
            )}
          </g>
        );
      })}

      {/* Nodes */}
      {nodes.map((node) => {
        const nx = getNodeX(node.id);
        const ny = getNodeY(node.id);
        const isBroken = node.status === "BROKEN";
        const isPartOfRoute = activeRoute.includes(node.id);
        const isRecovery = recoveryNodes.has(node.id);

        const fillColor = isBroken
          ? "#ef4444"
          : isPartOfRoute
          ? "#10b981"
          : isRecovery
          ? "#d97706"
          : "#2563eb";

        return (
          <g key={node.id} className="cursor-pointer">
            {isPartOfRoute && !isBroken && (
              <circle
                cx={nx}
                cy={ny}
                r="13"
                fill="#10b981"
                opacity="0.25"
                className="animate-ping"
              />
            )}
            <circle
              cx={nx}
              cy={ny}
              r={isBroken ? 9 : 7}
              fill={fillColor}
              stroke="#ffffff"
              strokeWidth="2.5"
            />
            <rect
              x={nx - 36}
              y={ny - 24}
              width="72"
              height="15"
              rx="3"
              fill="#ffffff"
              stroke="#cbd5e1"
              strokeWidth="0.8"
              opacity="0.95"
            />
            <text
              x={nx}
              y={ny - 13}
              textAnchor="middle"
              fontSize="9"
              fontWeight="600"
              fontFamily="ui-monospace, monospace"
              fill={isBroken ? "#dc2626" : "#0f172a"}
            >
              {node.id}
            </text>
            <title>{`${node.id}: ${node.status} (${node.x}, ${node.y})`}</title>
          </g>
        );
      })}
    </svg>
  );
}

