"use client";

import { useMemo } from "react";

export default function LiveMeshFigure({ mesh = { nodes: [], links: [] }, activeRecovery = null }) {
  const { nodes, links, minX, maxX, minY, maxY } = useMemo(() => {
    const rawNodes = mesh.nodes || [];
    const rawLinks = mesh.links || [];

    if (rawNodes.length === 0) {
      return { nodes: [], links: [], minX: 0, maxX: 100, minY: 0, maxY: 100 };
    }

    const xs = rawNodes.map((n) => n.x);
    const ys = rawNodes.map((n) => n.y);

    return {
      nodes: rawNodes,
      links: rawLinks,
      minX: Math.min(...xs),
      maxX: Math.max(...xs),
      minY: Math.min(...ys),
      maxY: Math.max(...ys),
    };
  }, [mesh]);

  const pad = 28;
  const w = 460;
  const h = 200;
  const scaleX = (x) => pad + ((x - minX) / (maxX - minX || 1)) * (w - pad * 2);
  const scaleY = (y) => h - pad - ((y - minY) / (maxY - minY || 1)) * (h - pad * 2);

  const nodeMap = useMemo(() => {
    const m = {};
    nodes.forEach((n) => {
      m[n.id] = { ...n, sx: scaleX(n.x), sy: scaleY(n.y) };
    });
    return m;
  }, [nodes, minX, maxX, minY, maxY]);

  if (nodes.length === 0) {
    return (
      <div className="flex items-center justify-center h-full text-xs text-muted mono">
        Waiting for mesh nodes to initialize...
      </div>
    );
  }

  return (
    <svg
      viewBox={`0 0 ${w} ${h}`}
      className="w-full h-full"
      role="img"
      aria-label="Live RF Mesh Topology"
    >
      {/* Dynamic Peer-to-Peer Communication Links */}
      {links.map((link, idx) => {
        const u = nodeMap[link.source];
        const v = nodeMap[link.target];
        if (!u || !v) return null;

        const isRecoveryLink =
          activeRecovery &&
          ((link.source === activeRecovery.broken && link.target === activeRecovery.winner) ||
            (link.target === activeRecovery.broken && link.source === activeRecovery.winner));

        return (
          <line
            key={`mesh-link-${idx}`}
            x1={u.sx}
            y1={u.sy}
            x2={v.sx}
            y2={v.sy}
            stroke={isRecoveryLink ? "#8a6d1f" : "#c9c9bc"}
            strokeWidth={isRecoveryLink ? "2.5" : "1.25"}
            strokeDasharray={isRecoveryLink ? "4 3" : undefined}
          />
        );
      })}

      {/* Nodes (Trucks) */}
      {nodes.map((n) => {
        const pt = nodeMap[n.id];
        if (!pt) return null;
        const isBroken = n.status === "BROKEN";

        return (
          <g key={n.id}>
            <circle
              cx={pt.sx}
              cy={pt.sy}
              r={isBroken ? 6 : 4.5}
              fill={isBroken ? "#a13a2e" : "#2e6b34"}
              stroke="#fbfbf8"
              strokeWidth="1.5"
            />
            <text
              x={pt.sx}
              y={pt.sy - 8}
              textAnchor="middle"
              className="mono"
              fontSize="9"
              fontWeight="600"
              fill={isBroken ? "#a13a2e" : "#181a16"}
            >
              {n.id.replace("TRUCK_", "T")}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
