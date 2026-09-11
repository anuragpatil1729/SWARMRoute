"use client";

import { useEffect, useRef } from "react";
import "leaflet/dist/leaflet.css";

const PALETTE = [
  "#2563eb", // Blue
  "#16a34a", // Green
  "#9333ea", // Purple
  "#d97706", // Amber
  "#0891b2", // Cyan
  "#e11d48", // Rose
];

// Logistics hub reference coordinate (San Francisco / Bay Area)
const BASE_LAT = 37.7749;
const BASE_LNG = -122.4194;

function toLatLng(x, y) {
  const lat = BASE_LAT + (y - 50) * 0.0025;
  const lng = BASE_LNG + (x - 40) * 0.0035;
  return [lat, lng];
}

export default function OpenStreetMap({
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
  const mapContainerRef = useRef(null);
  const mapInstanceRef = useRef(null);
  const layersRef = useRef({
    routes: [],
    recoveryRoutes: [],
    traffic: [],
    customers: [],
    depot: null,
    vehicles: {},
  });

  // Initialize Leaflet Map once
  useEffect(() => {
    if (typeof window === "undefined" || !mapContainerRef.current) return;

    let L;
    let isCancelled = false;

    import("leaflet").then((leaflet) => {
      if (isCancelled || !mapContainerRef.current) return;
      L = leaflet.default || leaflet;

      if (!mapInstanceRef.current) {
        const depotPos = toLatLng(depot?.x ?? 40, depot?.y ?? 50);
        const map = L.map(mapContainerRef.current, {
          center: depotPos,
          zoom: 13,
          zoomControl: true,
          attributionControl: true,
        });

        // OpenStreetMap Standard Tile Layer
        L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
          maxZoom: 19,
          attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        }).addTo(map);

        mapInstanceRef.current = map;
      }
    });

    return () => {
      isCancelled = true;
      if (mapInstanceRef.current) {
        mapInstanceRef.current.remove();
        mapInstanceRef.current = null;
      }
    };
  }, []);

  // Update Map Layers dynamically whenever state changes
  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map) return;

    import("leaflet").then((leaflet) => {
      const L = leaflet.default || leaflet;
      const layers = layersRef.current;

      // 1. Clear old route and traffic lines
      layers.routes.forEach((l) => l.remove());
      layers.routes = [];

      layers.recoveryRoutes.forEach((l) => l.remove());
      layers.recoveryRoutes = [];

      layers.traffic.forEach((l) => l.remove());
      layers.traffic = [];

      layers.customers.forEach((l) => l.remove());
      layers.customers = [];

      if (layers.depot) {
        layers.depot.remove();
        layers.depot = null;
      }

      const coordsById = {};
      if (depot) coordsById[0] = depot;
      customers.forEach((c) => {
        coordsById[c.id] = c;
      });

      // 2. Draw Depot
      if (depot) {
        const depotPos = toLatLng(depot.x, depot.y);
        const depotIcon = L.divIcon({
          className: "depot-marker",
          html: `<div style="background:#dc2626; color:white; font-size:10px; font-weight:700; padding:2px 6px; border-radius:4px; border:2px solid white; box-shadow:0 2px 4px rgba(0,0,0,0.3); text-align:center;">DEPOT</div>`,
          iconSize: [52, 20],
          iconAnchor: [26, 10],
        });
        layers.depot = L.marker(depotPos, { icon: depotIcon }).addTo(map);
        layers.depot.bindPopup("<b>Central Logistics Depot</b><br/>Coordinates: (" + depot.x + ", " + depot.y + ")");
      }

      // 3. Draw Customer Stops
      customers.forEach((c) => {
        const pos = toLatLng(c.x, c.y);
        const isDelivered = c.status === "DELIVERED";
        const isLate = c.status === "LATE";
        const color = isDelivered ? "#16a34a" : isLate ? "#dc2626" : "#64748b";

        const marker = L.circleMarker(pos, {
          radius: isDelivered ? 6 : 5,
          fillColor: color,
          color: "#ffffff",
          weight: 2,
          opacity: 1,
          fillOpacity: 0.9,
        }).addTo(map);

        marker.bindPopup(
          `<b>Customer #${c.id}</b><br/>Order: ${c.order_id || "ORD_" + c.id}<br/>Demand: ${c.demand} kg<br/>Status: <span style="color:${color};font-weight:bold">${c.status || "PENDING"}</span>`
        );
        marker.on("click", () => {
          if (onSelectOrder) onSelectOrder(c.order_id || `ORD_${c.id}`);
        });

        layers.customers.push(marker);
      });

      // 4. Draw Traffic Congested Roads
      trafficEdges.forEach((te) => {
        const c1 = coordsById[te.u];
        const c2 = coordsById[te.v];
        if (!c1 || !c2) return;
        const pts = [toLatLng(c1.x, c1.y), toLatLng(c2.x, c2.y)];
        const line = L.polyline(pts, {
          color: "#dc2626",
          weight: 6,
          opacity: 0.7,
          dashArray: "6, 6",
        }).addTo(map);
        line.bindPopup(`<b>Traffic Congestion</b><br/>Road: ${te.u} &rarr; ${te.v}<br/>Level: ${te.level} (${te.speed} km/h)`);
        layers.traffic.push(line);
      });

      // 5. Draw Active Vehicle Tour Polylines
      const routeList = Array.isArray(routes)
        ? routes.map((r, i) => ({
            id: r.truckId !== undefined ? `TRUCK_${r.truckId}` : `R_${i}`,
            stops: r.stops || r,
          }))
        : Object.entries(routes).map(([k, v]) => ({ id: k, stops: v }));

      routeList.forEach((r, idx) => {
        const color = PALETTE[idx % PALETTE.length];
        const isDimmed = selectedVehicleId && selectedVehicleId !== r.id;

        const pts = (r.stops || [])
          .map((id) => coordsById[id])
          .filter(Boolean)
          .map((c) => toLatLng(c.x, c.y));

        if (pts.length < 2) return;

        const line = L.polyline(pts, {
          color: color,
          weight: isDimmed ? 2 : 4,
          opacity: isDimmed ? 0.2 : 0.85,
          smoothFactor: 1,
        }).addTo(map);

        line.bindPopup(`<b>${r.id} Tour</b><br/>Stops: ${r.stops.length - 2}<br/>Color: ${color}`);
        layers.routes.push(line);
      });

      // 6. Draw Recovery Reassigned Routes (Dashed Amber)
      Object.entries(recoveryRoutes).forEach(([truckId, stopIds]) => {
        const pts = stopIds
          .map((id) => coordsById[id])
          .filter(Boolean)
          .map((c) => toLatLng(c.x, c.y));

        if (pts.length < 2) return;

        const line = L.polyline(pts, {
          color: "#d97706",
          weight: 5,
          dashArray: "8, 6",
          opacity: 0.95,
        }).addTo(map);

        line.bindPopup(`<b>Peer Recovery Route: ${truckId}</b><br/>Autonomous Contract-Net Auction Detour`);
        layers.recoveryRoutes.push(line);
      });

      // 7. Draw or Update Moving Truck Markers
      const currentVehIds = new Set(vehicles.map((v) => v.id));

      // Remove vanished vehicles
      Object.keys(layers.vehicles).forEach((vid) => {
        if (!currentVehIds.has(vid)) {
          layers.vehicles[vid].remove();
          delete layers.vehicles[vid];
        }
      });

      vehicles.forEach((v, idx) => {
        const pos = toLatLng(v.x, v.y);
        const isBroken = v.status === "BROKEN_DOWN";
        const color = isBroken ? "#dc2626" : PALETTE[idx % PALETTE.length];
        const isSelected = selectedVehicleId === v.id;

        const truckIcon = L.divIcon({
          className: "truck-marker",
          html: `
            <div style="
              display: flex;
              align-items: center;
              gap: 4px;
              background: ${isBroken ? "#dc2626" : color};
              color: white;
              padding: 3px 8px;
              border-radius: 9999px;
              border: 2px solid white;
              box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.3);
              font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
              font-size: 11px;
              font-weight: 700;
              white-space: nowrap;
              transform: ${isSelected ? "scale(1.2)" : "scale(1)"};
              transition: all 0.2s ease;
            ">
              <span>${isBroken ? "⚠" : "🚚"}</span>
              <span>${v.id.replace("TRUCK_", "T")}</span>
              <span style="opacity:0.85; font-size:10px;">${isBroken ? "FAULT" : Math.round(v.speed_kmh) + "km/h"}</span>
            </div>
          `,
          iconSize: [85, 26],
          iconAnchor: [42, 13],
        });

        if (layers.vehicles[v.id]) {
          layers.vehicles[v.id].setLatLng(pos);
          layers.vehicles[v.id].setIcon(truckIcon);
        } else {
          const marker = L.marker(pos, { icon: truckIcon }).addTo(map);
          marker.on("click", () => {
            if (onSelectVehicle) onSelectVehicle(v.id);
          });
          layers.vehicles[v.id] = marker;
        }

        layers.vehicles[v.id].bindPopup(`
          <div style="font-family: sans-serif; font-size: 12px; line-height: 1.4;">
            <b style="color:${color}; font-size:13px;">${v.id}</b><br/>
            Status: <b>${v.status}</b><br/>
            Speed: ${v.speed_kmh} km/h<br/>
            Progress: ${v.route_progress}%<br/>
            Load: ${v.current_load} / ${v.max_weight} kg<br/>
            Fuel: ${v.fuel_level} L | CO2: ${v.co2_kg} kg
          </div>
        `);
      });
    });
  }, [customers, depot, routes, recoveryRoutes, vehicles, trafficEdges, selectedVehicleId, onSelectVehicle, onSelectOrder]);

  return (
    <div className="w-full h-[520px] rounded-xl overflow-hidden shadow-sm border border-slate-200 relative">
      <div ref={mapContainerRef} className="w-full h-full z-0" />
      {/* Interactive Legend Overlay */}
      <div className="absolute top-3 right-3 z-[1000] bg-white/95 backdrop-blur-sm px-3 py-2 rounded-lg shadow border border-slate-200 text-xs font-mono space-y-1">
        <div className="flex items-center gap-2">
          <span className="w-3 h-3 bg-red-600 rounded-sm inline-block" />
          <span className="text-slate-800 font-semibold">Depot</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="w-2.5 h-2.5 bg-green-600 rounded-full inline-block" />
          <span className="text-slate-600">Delivered</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="w-2.5 h-2.5 bg-slate-500 rounded-full inline-block" />
          <span className="text-slate-600">Pending</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="w-3 h-1 bg-amber-500 inline-block" />
          <span className="text-amber-700 font-semibold">Recovery Route</span>
        </div>
      </div>
    </div>
  );
}
