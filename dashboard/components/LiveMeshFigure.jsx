"use client";

import { useMemo } from "react";

export default function LiveMeshFigure({ mesh = {}, cloudStatus, activeRecovery }) {
  const nodes = mesh.nodes || []; const links = mesh.links || [];
  const layout = useMemo(() => { if (!nodes.length) return null; const xs = nodes.map((node) => node.x); const ys = nodes.map((node) => node.y); return { minX: Math.min(...xs), maxX: Math.max(...xs), minY: Math.min(...ys), maxY: Math.max(...ys) }; }, [nodes]);
  if (!layout) return <div className="ops-map-empty">No mesh nodes supplied by the simulation.</div>;
  const width = 560; const height = 240; const pad = 34; const px = (value) => pad + ((value - layout.minX) / (layout.maxX - layout.minX || 1)) * (width - pad * 2); const py = (value) => height - pad - ((value - layout.minY) / (layout.maxY - layout.minY || 1)) * (height - pad * 2); const indexed = Object.fromEntries(nodes.map((node) => [node.id, node]));
  const recoveryNodes = new Set([activeRecovery?.vehicle_id || activeRecovery?.broken, activeRecovery?.recovery_vehicle || activeRecovery?.winner].filter(Boolean));
  return <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-full" role="img" aria-label={`Mesh topology; cloud is ${cloudStatus || "not reported"}`}>
    <rect x="0" y="0" width={width} height={height} fill="#f8fafc" /><text x={pad} y="20" fontSize="10" fontFamily="ui-monospace, monospace" fill="#475569">CLOUD: {cloudStatus || "—"}</text>
    {links.map((link, index) => { const source = indexed[link.source]; const target = indexed[link.target]; if (!source || !target) return null; const recovery = recoveryNodes.has(link.source) && recoveryNodes.has(link.target); return <line key={`${link.source}-${link.target}-${index}`} x1={px(source.x)} y1={py(source.y)} x2={px(target.x)} y2={py(target.y)} stroke={recovery ? "#b45309" : "#94a3b8"} strokeWidth={recovery ? "3" : "1.5"} strokeDasharray={recovery ? "6 3" : undefined}><title>{`${link.source} to ${link.target}${link.distance !== undefined ? `, ${link.distance} km` : ""}`}</title></line>; })}
    {nodes.map((node) => <g key={node.id}><circle cx={px(node.x)} cy={py(node.y)} r={node.status === "BROKEN" ? 8 : 6} fill={node.status === "BROKEN" ? "#dc2626" : recoveryNodes.has(node.id) ? "#b45309" : "#2563eb"} stroke="#fff" strokeWidth="2" /><text x={px(node.x)} y={py(node.y) - 11} textAnchor="middle" fontSize="10" fontFamily="ui-monospace, monospace" fill="#0f172a">{node.id}</text><title>{`${node.id}: ${node.status}`}</title></g>)}
  </svg>;
}
