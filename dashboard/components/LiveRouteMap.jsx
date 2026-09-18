"use client";

import { useMemo, useState } from "react";

const palette = ["#2563eb", "#0f766e", "#7c3aed", "#0369a1", "#4d7c0f", "#b45309"];

export default function LiveRouteMap({ customers = [], depot, routes = {}, recoveryRoutes = {}, vehicles = [], trafficEdges = [], selectedVehicleId, onSelectVehicle }) {
  const [localSelection, setLocalSelection] = useState(null);
  const selected = selectedVehicleId ?? localSelection;
  const geometry = useMemo(() => {
    const nodes = {}; const points = [];
    if (depot && Number.isFinite(depot.x) && Number.isFinite(depot.y)) { nodes[0] = depot; points.push(depot); }
    customers.forEach((customer) => { if (Number.isFinite(customer.x) && Number.isFinite(customer.y)) { nodes[customer.id] = customer; points.push(customer); } });
    vehicles.forEach((vehicle) => { if (Number.isFinite(vehicle.x) && Number.isFinite(vehicle.y)) points.push(vehicle); });
    if (!points.length) return null;
    return { nodes, minX: Math.min(...points.map((point) => point.x)), maxX: Math.max(...points.map((point) => point.x)), minY: Math.min(...points.map((point) => point.y)), maxY: Math.max(...points.map((point) => point.y)) };
  }, [customers, depot, vehicles]);
  if (!geometry) return <div className="ops-map-empty">Map geometry has not been supplied by the simulation.</div>;
  const { nodes, minX, maxX, minY, maxY } = geometry; const width = 720; const height = 480; const pad = 34;
  const x = (value) => pad + ((value - minX) / (maxX - minX || 1)) * (width - 2 * pad);
  const y = (value) => height - pad - ((value - minY) / (maxY - minY || 1)) * (height - 2 * pad);
  const path = (stops) => stops.map((id) => nodes[id]).filter(Boolean).map((node) => `${x(node.x)},${y(node.y)}`).join(" ");
  const choose = (id) => { const next = selected === id ? null : id; setLocalSelection(next); onSelectVehicle?.(next); };
  return <div className="live-route-map">
    <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-full" role="img" aria-label="Simulation route map with fleet positions, delivery nodes, routes, traffic, and recovery routes">
      <rect x={pad} y={pad} width={width - pad * 2} height={height - pad * 2} fill="#f8fafc" stroke="#cbd5e1" />
      {Array.from({ length: 7 }).map((_, index) => <line key={`vertical-${index}`} x1={pad + index * (width - 2 * pad) / 6} x2={pad + index * (width - 2 * pad) / 6} y1={pad} y2={height - pad} stroke="#e2e8f0" />)}
      {Array.from({ length: 6 }).map((_, index) => <line key={`horizontal-${index}`} x1={pad} x2={width - pad} y1={pad + index * (height - 2 * pad) / 5} y2={pad + index * (height - 2 * pad) / 5} stroke="#e2e8f0" />)}
      {Object.entries(routes).map(([id, stops], index) => { const points = path(stops); if (!points) return null; return <polyline key={id} points={points} fill="none" stroke={palette[index % palette.length]} strokeWidth={selected && selected !== id ? 1.5 : 2.5} opacity={selected && selected !== id ? .16 : .75} strokeLinejoin="round" />; })}
      {trafficEdges.map((edge, index) => { const source = nodes[edge.u]; const target = nodes[edge.v]; return source && target ? <line key={`traffic-${index}`} x1={x(source.x)} y1={y(source.y)} x2={x(target.x)} y2={y(target.y)} stroke="#dc2626" strokeWidth="5" strokeDasharray="7 4" opacity=".7"><title>{`Traffic: ${edge.level || "congested"}`}</title></line> : null; })}
      {Object.entries(recoveryRoutes).map(([id, stops]) => { const points = path(stops); return points ? <polyline key={`recovery-${id}`} points={points} fill="none" stroke="#b45309" strokeWidth="3" strokeDasharray="8 5" strokeLinejoin="round"><title>{`Recovery route: ${id}`}</title></polyline> : null; })}
      {customers.map((customer) => Number.isFinite(customer.x) && Number.isFinite(customer.y) ? <g key={customer.id}><circle cx={x(customer.x)} cy={y(customer.y)} r={customer.status === "DELIVERED" ? 4 : 3.2} fill={customer.status === "DELIVERED" ? "#16a34a" : "#64748b"} /><title>{`${customer.order_id || customer.id}: ${customer.status || "unknown"}`}</title></g> : null)}
      {depot && Number.isFinite(depot.x) && Number.isFinite(depot.y) && <g><rect x={x(depot.x) - 6} y={y(depot.y) - 6} width="12" height="12" fill="#0f172a" /><text x={x(depot.x) + 9} y={y(depot.y) + 3} fontSize="10" fontFamily="ui-monospace, monospace" fill="#0f172a">DEPOT</text><title>Depot</title></g>}
      {vehicles.map((vehicle, index) => Number.isFinite(vehicle.x) && Number.isFinite(vehicle.y) ? <g key={vehicle.id} className="cursor-pointer" onClick={() => choose(vehicle.id)} tabIndex="0" role="button" aria-label={`Select ${vehicle.id}`} onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") choose(vehicle.id); }}>
        {selected === vehicle.id && <circle cx={x(vehicle.x)} cy={y(vehicle.y)} r="12" fill="none" stroke="#0f172a" strokeWidth="1.5" strokeDasharray="3 2" />}
        <circle cx={x(vehicle.x)} cy={y(vehicle.y)} r={vehicle.status === "BROKEN_DOWN" ? 7 : 6} fill={vehicle.status === "BROKEN_DOWN" ? "#dc2626" : palette[index % palette.length]} stroke="#fff" strokeWidth="2" /><text x={x(vehicle.x)} y={y(vehicle.y) + 3.5} textAnchor="middle" fontSize="8" fontWeight="700" fill="#fff">{vehicle.status === "BROKEN_DOWN" ? "!" : ""}</text><text x={x(vehicle.x) + 9} y={y(vehicle.y) - 8} fontSize="10" fontFamily="ui-monospace, monospace" fill="#0f172a">{vehicle.id}</text><title>{`${vehicle.id}: ${vehicle.status}`}</title>
      </g> : null)}
    </svg>
    <div className="ops-map-filter" aria-label="Vehicle map filter"><button onClick={() => choose(null)} className={!selected ? "is-selected" : ""}>All fleet</button>{vehicles.map((vehicle) => <button key={vehicle.id} onClick={() => choose(vehicle.id)} className={selected === vehicle.id ? "is-selected" : ""}>{vehicle.id}</button>)}</div>
  </div>;
}
