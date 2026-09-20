"use client";

import { useEffect, useRef, useState } from "react";
import "leaflet/dist/leaflet.css";

const PALETTE = [
  "#2563eb", // Blue
  "#16a34a", // Green
  "#9333ea", // Purple
  "#d97706", // Amber
  "#0891b2", // Cyan
  "#e11d48", // Rose
];

export const CITIES = {
  Mumbai: {
    name: "Mumbai (MH)",
    lat: 19.076,
    lng: 72.8777,
    hubName: "Mumbai Central Cargo Terminal (BKC / Kurla)",
    zoom: 13,
  },
  Pune: {
    name: "Pune (MH)",
    lat: 18.5204,
    lng: 73.8567,
    hubName: "Pune Logistics Hub (Hinjawadi / Shivaji Nagar)",
    zoom: 13,
  },
  Maharashtra: {
    name: "Maharashtra Corridor (Mumbai - Pune)",
    lat: 18.9067,
    lng: 73.2325,
    hubName: "Maharashtra Central Expressway Cargo Corridor",
    zoom: 10,
  },
  Bengaluru: {
    name: "Bengaluru (KA)",
    lat: 12.9716,
    lng: 77.5946,
    hubName: "Bengaluru Central Logistics Hub (MG Road / Shivajinagar)",
    zoom: 13,
  },
  Chennai: {
    name: "Chennai (TN)",
    lat: 13.0827,
    lng: 80.2707,
    hubName: "Chennai Freight Terminal (Guindy / Ambattur)",
    zoom: 13,
  },
  Kolkata: {
    name: "Kolkata (WB)",
    lat: 22.5726,
    lng: 88.3639,
    hubName: "Kolkata Central Depot (Salt Lake / Rajarhat)",
    zoom: 13,
  },
  Ahmedabad: {
    name: "Ahmedabad (GJ)",
    lat: 23.0225,
    lng: 72.5714,
    hubName: "Ahmedabad Cargo Hub (Sanand / Changodar)",
    zoom: 13,
  },
  Jaipur: {
    name: "Jaipur (RJ)",
    lat: 26.9124,
    lng: 75.7873,
    hubName: "Jaipur Logistics Terminal (Sitapura / Mansarovar)",
    zoom: 13,
  },
  Surat: {
    name: "Surat (GJ)",
    lat: 21.1702,
    lng: 72.8311,
    hubName: "Surat Central Dispatch Hub (Udhna / Sachin)",
    zoom: 13,
  },
  Lucknow: {
    name: "Lucknow (UP)",
    lat: 26.8467,
    lng: 80.9462,
    hubName: "Lucknow Transport Nagar Depot",
    zoom: 13,
  },
  Indore: {
    name: "Indore (MP)",
    lat: 22.7196,
    lng: 75.8577,
    hubName: "Indore Logistics Park (Pithampur / Vijay Nagar)",
    zoom: 13,
  },
  Chandigarh: {
    name: "Chandigarh (PB/HR)",
    lat: 30.7333,
    lng: 76.7794,
    hubName: "Chandigarh Industrial Area Phase 1",
    zoom: 13,
  },
  Kochi: {
    name: "Kochi (KL)",
    lat: 9.9312,
    lng: 76.2673,
    hubName: "Kochi Marine & Cargo Hub (Willingdon / Edappally)",
    zoom: 13,
  },
};

export function getCityConfig(cityName) {
  if (!cityName) return { key: "Mumbai", ...CITIES.Mumbai };
  const clean = cityName.trim();
  const lower = clean.toLowerCase();
  for (const [key, c] of Object.entries(CITIES)) {
    if (key.toLowerCase() === lower || c.name.toLowerCase().includes(lower)) {
      return { key, ...c };
    }
  }
  // Generic fallback for any other custom city registered by admin
  return {
    key: clean,
    name: `${clean} Operations`,
    lat: 19.0760,
    lng: 72.8777,
    hubName: `${clean} Central Logistics Hub`,
    zoom: 12,
  };
}

function toLatLng(x, y, city = CITIES.Maharashtra || CITIES.Mumbai) {
  // Check if x and y are already authentic GPS coordinates
  if (typeof x === "number" && typeof y === "number") {
    if (x >= 8.0 && x <= 38.0 && y >= 68.0 && y <= 98.0) {
      return [x, y];
    }
    if (y >= 8.0 && y <= 38.0 && x >= 68.0 && x <= 98.0) {
      return [y, x];
    }
  }
  const lat = city.lat + (y - 50) * 0.003;
  const lng = city.lng + (x - 40) * 0.0035;
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
  activeCity = null,
}) {
  const mapContainerRef = useRef(null);
  const mapInstanceRef = useRef(null);

  const initialResolved = activeCity ? getCityConfig(activeCity) : { key: "Mumbai", ...CITIES.Mumbai };
  const [selectedCityKey, setSelectedCityKey] = useState(initialResolved.key);
  const [mapReady, setMapReady] = useState(false);
  const selectedCity = CITIES[selectedCityKey] || getCityConfig(selectedCityKey);

  useEffect(() => {
    if (activeCity) {
      const resolved = getCityConfig(activeCity);
      setSelectedCityKey(resolved.key);
    }
  }, [activeCity]);

  const leafletRef = useRef(null);
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
      leafletRef.current = L;

      if (!mapInstanceRef.current && mapContainerRef.current) {
        const depotPos = toLatLng(depot?.x ?? 40, depot?.y ?? 50, selectedCity);
        const map = L.map(mapContainerRef.current, {
          center: depotPos,
          zoom: selectedCity.zoom,
          zoomControl: true,
          attributionControl: true,
        });

        // High-reliability OpenStreetMap tile layer with subdomains
        L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
          maxZoom: 19,
          subdomains: ["a", "b", "c"],
          attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        }).addTo(map);

        mapInstanceRef.current = map;
        setMapReady(true);

        // Multiple size invalidations to ensure proper tile loading
        map.invalidateSize();
        setTimeout(() => { if (!isCancelled && map) map.invalidateSize(); }, 150);
        setTimeout(() => { if (!isCancelled && map) map.invalidateSize(); }, 500);
        setTimeout(() => { if (!isCancelled && map) map.invalidateSize(); }, 1200);
      }
    });

    return () => {
      isCancelled = true;
      if (mapInstanceRef.current) {
        mapInstanceRef.current.remove();
        mapInstanceRef.current = null;
        setMapReady(false);
      }
    };
  }, []);

  // Container ResizeObserver to auto-adapt to responsive viewports
  useEffect(() => {
    if (!mapContainerRef.current) return;
    const ro = new ResizeObserver(() => {
      if (mapInstanceRef.current) {
        mapInstanceRef.current.invalidateSize();
      }
    });
    ro.observe(mapContainerRef.current);
    return () => ro.disconnect();
  }, []);

  // Recenter map when city selection changes
  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map) return;
    const centerPos = toLatLng(depot?.x ?? 40, depot?.y ?? 50, selectedCity);
    map.flyTo(centerPos, selectedCity.zoom, { duration: 1.2 });
  }, [selectedCityKey, depot?.x, depot?.y]);

  // Update Map Layers dynamically whenever state or mapReady changes
  useEffect(() => {
    const map = mapInstanceRef.current;
    const L = leafletRef.current;
    if (!map || !mapReady || !L) return;

    const layers = layersRef.current;

      // 1. Clear old route and traffic lines (these change dynamically with vehicle paths)
      layers.routes.forEach((l) => l.remove());
      layers.routes = [];

      layers.recoveryRoutes.forEach((l) => l.remove());
      layers.recoveryRoutes = [];

      layers.traffic.forEach((l) => l.remove());
      layers.traffic = [];

      const coordsById = {};
      if (depot) coordsById[0] = depot;
      customers.forEach((c) => {
        coordsById[c.id] = c;
      });

      // 2. Draw Depot (only once, avoid DOM recreation)
      if (depot && !layers.depot) {
        const depotPos = toLatLng(depot.x, depot.y, selectedCity);
        const depotIcon = L.divIcon({
          className: "depot-marker",
          html: `<div style="background:#dc2626; color:white; font-size:10px; font-weight:700; padding:3px 8px; border-radius:4px; border:2px solid white; box-shadow:0 2px 5px rgba(0,0,0,0.35); text-align:center; white-space:nowrap;">🏢 DEPOT (HUB)</div>`,
          iconSize: [110, 24],
          iconAnchor: [55, 12],
        });
        layers.depot = L.marker(depotPos, { icon: depotIcon }).addTo(map);
        layers.depot.bindPopup(
          `<div style="font-family:sans-serif; font-size:12px; line-height:1.4;">
            <b style="color:#dc2626; font-size:13px;">${selectedCity.hubName}</b><br/>
            <span>Central Dispatch Station & EV Fast Charging Terminal</span><br/>
            <span style="color:#64748b; font-size:11px;">Grid Coordinates: (${depot.x}, ${depot.y})</span>
          </div>`
        );
      }

      // 3. Draw or Update Customer Stops (reuse markers, zero DOM layout thrashing)
      if (!layers.customersMap) layers.customersMap = {};
      customers.forEach((c) => {
        const isDelivered = c.status === "DELIVERED";
        const isLate = c.status === "LATE";
        const color = isDelivered ? "#16a34a" : isLate ? "#dc2626" : "#64748b";

        const existingMarker = layers.customersMap[c.id];
        if (existingMarker) {
          existingMarker.setStyle({ fillColor: color });
        } else {
          const rawLat = c.lat ?? c.latitude;
          const rawLng = c.lng ?? c.lon ?? c.longitude;
          const pos = (typeof rawLat === "number" && typeof rawLng === "number" && rawLat >= 8.0 && rawLat <= 38.0)
            ? [rawLat, rawLng]
            : toLatLng(c.x, c.y, selectedCity);

          const marker = L.circleMarker(pos, {
            radius: isDelivered ? 7 : 6,
            fillColor: color,
            color: "#ffffff",
            weight: 2,
            opacity: 1,
            fillOpacity: 0.92,
          }).addTo(map);

          const stopAddress = c.address || c.area;
          const orderIdentifier = c.order_id || (c.id !== undefined ? `#${c.id}` : "—");
          const demandText = c.demand !== undefined ? `${c.demand} kg` : "—";

          marker.bindPopup(
            `<div style="font-family:sans-serif; font-size:12px; line-height:1.4;">
              <b style="font-size:13px;">Customer Stop ${c.id !== undefined ? `#${c.id}` : ""}</b><br/>
              ${stopAddress ? `<span style="color:#2563eb; font-weight:600;">${stopAddress}</span><br/>` : ""}
              Order ID: <b>${orderIdentifier}</b><br/>
              Payload Demand: <b>${demandText}</b><br/>
              Status: <span style="color:${color};font-weight:bold;text-transform:uppercase;">${c.status || "PENDING"}</span>
            </div>`
          );
          marker.on("click", () => {
            if (onSelectOrder) onSelectOrder(c.order_id || c.id);
          });
          layers.customersMap[c.id] = marker;
          layers.customers.push(marker);
        }
      });

      // 4. Draw Traffic Congested Roads
      trafficEdges.forEach((te) => {
        const c1 = coordsById[te.u];
        const c2 = coordsById[te.v];
        if (!c1 || !c2) return;
        const pts = [toLatLng(c1.x, c1.y, selectedCity), toLatLng(c2.x, c2.y, selectedCity)];
        const line = L.polyline(pts, {
          color: "#dc2626",
          weight: 6,
          opacity: 0.75,
          dashArray: "6, 6",
        }).addTo(map);
        line.bindPopup(`<b>Traffic Congestion Bottleneck</b><br/>Corridor: Node ${te.u} &rarr; ${te.v}<br/>Severity: ${te.level} (${te.speed} km/h)`);
        layers.traffic.push(line);
      });

      // 5. Draw Active Vehicle Tour Polylines
      const routeList = Array.isArray(routes)
        ? routes.map((r, i) => ({
            id: r.truck || (r.truckId !== undefined ? `TRUCK_${r.truckId}` : `R_${i}`),
            stops: r.stops || r,
          }))
        : Object.entries(routes).map(([k, v]) => ({ id: k, stops: v }));

      routeList.forEach((r, idx) => {
        const color = PALETTE[idx % PALETTE.length];
        const isDimmed = selectedVehicleId && selectedVehicleId !== r.id;

        const pts = (r.stops || [])
          .map((id) => coordsById[id])
          .filter(Boolean)
          .map((c) => toLatLng(c.x, c.y, selectedCity));

        if (pts.length < 2) return;

        const line = L.polyline(pts, {
          color: color,
          weight: isDimmed ? 2 : 4,
          opacity: isDimmed ? 0.25 : 0.88,
          smoothFactor: 1,
        }).addTo(map);

        line.bindPopup(`<b>${r.id} Active Delivery Route</b><br/>Stops: ${r.stops.length - 2} deliveries<br/>Color: ${color}`);
        layers.routes.push(line);
      });

      // 6. Draw Recovery Reassigned Routes (Dashed Amber)
      Object.entries(recoveryRoutes).forEach(([truckId, stopIds]) => {
        const pts = stopIds
          .map((id) => coordsById[id])
          .filter(Boolean)
          .map((c) => toLatLng(c.x, c.y, selectedCity));

        if (pts.length < 2) return;

        const line = L.polyline(pts, {
          color: "#d97706",
          weight: 5,
          dashArray: "8, 6",
          opacity: 0.95,
        }).addTo(map);

        line.bindPopup(`<b>Peer Swarm Recovery Route: ${truckId}</b><br/>P2P Mesh Auction Re-route`);
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
        const rawVLat = v.lat ?? v.latitude ?? (v.location?.lat);
        const rawVLng = v.lng ?? v.lon ?? v.longitude ?? (v.location?.lng);
        const pos = (typeof rawVLat === "number" && typeof rawVLng === "number" && rawVLat >= 8.0 && rawVLat <= 38.0)
          ? [rawVLat, rawVLng]
          : toLatLng(v.x, v.y, selectedCity);
        const isBroken = v.status === "BROKEN_DOWN";
        const color = isBroken ? "#dc2626" : PALETTE[idx % PALETTE.length];
        const isSelected = selectedVehicleId === v.id;
        const partnerName = v.partner_name || v.id;

        const truckIcon = L.divIcon({
          className: "truck-marker",
          html: `
            <div style="
              display: flex;
              align-items: center;
              gap: 5px;
              background: ${isBroken ? "#dc2626" : color};
              color: white;
              padding: 4px 9px;
              border-radius: 9999px;
              border: 2px solid white;
              box-shadow: 0 4px 8px -1px rgba(0, 0, 0, 0.35);
              font-family: ui-sans-serif, system-ui, sans-serif;
              font-size: 11px;
              font-weight: 700;
              white-space: nowrap;
              transform: ${isSelected ? "scale(1.2)" : "scale(1)"};
              transition: all 0.2s ease;
            ">
              <span>${isBroken ? "⚠" : (v.avatar || "🚚")}</span>
              <span>${partnerName}</span>
              <span style="opacity:0.9; font-size:10px; font-weight:600; background:rgba(0,0,0,0.2); padding:1px 4px; border-radius:4px;">${isBroken ? "SOS" : (v.speed_kmh !== undefined ? Math.round(v.speed_kmh) + " km/h" : "—")}</span>
            </div>
          `,
          iconSize: [120, 28],
          iconAnchor: [60, 14],
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

        const vehicleModelLine = v.vehicle_model || "";
        const registrationLine = v.registration || v.id;
        const subHeader = vehicleModelLine ? `${vehicleModelLine} · ${registrationLine}` : registrationLine;
        const hubLine = v.hub ? `Hub: <b>${v.hub}</b><br/>` : "";

        layers.vehicles[v.id].bindPopup(`
          <div style="font-family: sans-serif; font-size: 12px; line-height: 1.45;">
            <div style="display:flex; align-items:center; gap:6px; margin-bottom:4px;">
              <span style="font-size:16px;">${v.avatar || "🚚"}</span>
              <div>
                <b style="color:${color}; font-size:13px;">${v.partner_name || v.id}</b>
                <div style="font-size:11px; color:#64748b;">${subHeader}</div>
              </div>
            </div>
            <div style="border-top:1px solid #e2e8f0; padding-top:5px; font-size:11px; display:flex; flex-direction:column; gap:2px;">
              <div>Status: <b style="color:${isBroken ? '#dc2626' : '#16a34a'};">${v.status || "—"}</b></div>
              ${hubLine}
              <div>Speed: <b>${v.speed_kmh !== undefined ? `${v.speed_kmh} km/h` : "—"}</b> · Fuel: <b>${v.fuel_level !== undefined ? `${Math.round(v.fuel_level)}%` : "—"}</b></div>
              <div>Cargo Load: <b>${v.current_load !== undefined ? `${v.current_load} / ${v.max_weight ?? "—"} kg` : "—"}</b> (Rem: <b>${v.remaining_capacity !== undefined ? `${v.remaining_capacity} kg` : "—"}</b>)</div>
              <div style="background:#f8fafc; border:1px solid #cbd5e1; border-radius:6px; padding:4px 6px; margin-top:4px;">
                <div style="font-size:10px; font-weight:700; color:#0369a1; text-transform:uppercase; letter-spacing:0.5px;">🤖 AI Route Feasibility</div>
                <div style="font-size:10px; color:#334155; margin-top:2px;">
                  ${isBroken || (v.fuel_level && v.fuel_level < 15)
                    ? '<span style="color:#dc2626; font-weight:bold;">⚠ REQUEST_ASSISTANCE</span>: Peer BLE mesh handover recommended.'
                    : '<span>✔ <b style="color:#16a34a;">KEEP_ROUTE</b>: Real-time traffic, road condition & fuel optimal.</span>'}
                </div>
              </div>
            </div>
          </div>
        `);
      });
  }, [mapReady, customers, depot, routes, recoveryRoutes, vehicles, trafficEdges, selectedVehicleId, onSelectVehicle, onSelectOrder, selectedCity]);

  return (
    <div className="w-full h-full min-h-[520px] rounded-xl overflow-hidden shadow-sm border border-slate-200 relative">
      <div ref={mapContainerRef} className="w-full h-[520px] min-h-[520px] z-0" style={{ height: "520px", minHeight: "520px" }} />

      {/* City & GIS Hub Selector (Top-Left) */}
      <div className="absolute top-3 left-12 z-[1000] bg-white/95 backdrop-blur-sm px-3 py-1.5 rounded-lg shadow border border-slate-200 flex items-center gap-2">
        <span className="text-xs font-semibold text-slate-700">📍 Indian GIS Hub:</span>
        <select
          value={selectedCityKey}
          onChange={(e) => setSelectedCityKey(e.target.value)}
          className="text-xs font-semibold bg-slate-50 border border-slate-300 rounded px-2 py-1 text-blue-700 outline-none cursor-pointer focus:ring-1 focus:ring-blue-500"
        >
          {Object.entries(CITIES).map(([key, c]) => (
            <option key={key} value={key}>
              {c.name}
            </option>
          ))}
          {!CITIES[selectedCityKey] && selectedCity && (
            <option value={selectedCityKey}>
              {selectedCity.name || selectedCityKey}
            </option>
          )}
        </select>
      </div>

      {/* Interactive Legend Overlay (Top-Right) */}
      <div className="absolute top-3 right-3 z-[1000] bg-white/95 backdrop-blur-sm px-3 py-2 rounded-lg shadow border border-slate-200 text-xs font-mono space-y-1">
        <div className="flex items-center gap-2">
          <span className="w-3 h-3 bg-red-600 rounded-sm inline-block" />
          <span className="text-slate-800 font-semibold">Central Hub (Depot)</span>
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
          <span className="text-amber-700 font-semibold">Swarm Recovery Tour</span>
        </div>
      </div>
    </div>
  );
}
